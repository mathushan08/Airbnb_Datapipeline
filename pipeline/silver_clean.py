"""
Silver Layer — Data Cleaning & Standardization

Reads raw Bronze files, applies systematic cleaning, and writes
clean Parquet files to data/silver/<city>/.
"""

import os
import re
import gzip
import json
import yaml
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from pathlib import Path
from loguru import logger

from pipeline.metadata import MetadataManager
from pipeline.validator import ListingValidator, CalendarValidator, print_validation_report


# Constants

# Standardized room type mapping
ROOM_TYPE_MAP = {
    "entire home/apt":  "Entire home/apt",
    "entire home":      "Entire home/apt",
    "private room":     "Private room",
    "shared room":      "Shared room",
    "hotel room":       "Hotel room",
}

# Property type normalization — collapse 50+ variants into ~10 categories
PROPERTY_TYPE_MAP = {
    "entire apartment":         "Apartment",
    "private room in apartment": "Apartment",
    "shared room in apartment": "Apartment",
    "entire condominium":       "Apartment",
    "entire residential home":  "House",
    "entire house":             "House",
    "private room in house":    "House",
    "shared room in house":     "House",
    "entire townhouse":         "Townhouse",
    "entire loft":              "Loft",
    "private room in loft":     "Loft",
    "entire serviced apartment": "Serviced Apartment",
    "entire guest suite":       "Guest Suite",
    "private room in guest suite": "Guest Suite",
    "room in boutique hotel":   "Hotel",
    "entire hotel":             "Hotel",
    "private room in hostel":   "Hostel",
    "shared room in hostel":    "Hostel",
    "entire villa":             "Villa",
    "entire cottage":           "Cottage",
    "entire bungalow":          "Bungalow",
    "boat":                     "Unique",
    "treehouse":                "Unique",
    "camper/rv":                "Unique",
    "tent":                     "Unique",
}


# Utility functions

def parse_price(price_series: pd.Series) -> pd.Series:
    """
    Clean price columns: strip '$', ',', whitespace → float.
    Invalid values become NaN.

    Examples:
        "$1,200.00" → 1200.0
        "150"       → 150.0
        "N/A"       → NaN
    """
    return (
        price_series
        .astype(str)
        .str.replace(r"[\$,\s]", "", regex=True)
        .str.strip()
        .replace({"nan": np.nan, "None": np.nan, "": np.nan})
        .pipe(pd.to_numeric, errors="coerce")
    )


def parse_date(date_series: pd.Series) -> pd.Series:
    """
    Parse date strings into datetime64[ns].
    Returns NaT for unparseable values.
    """
    return pd.to_datetime(date_series, errors="coerce", infer_datetime_format=True)


def normalize_room_type(rt_series: pd.Series) -> pd.Series:
    """
    Normalize room_type to 4 standard categories.
    Unknown values are kept as-is with a warning.
    """
    normalized = rt_series.str.lower().str.strip().map(ROOM_TYPE_MAP)
    unknown = rt_series[normalized.isna() & rt_series.notna()].unique()
    if len(unknown) > 0:
        logger.warning(f"Unknown room types (kept as-is): {unknown[:5]}")
    # Fill unknowns with original value (title-cased)
    return normalized.fillna(rt_series.str.title())


def normalize_property_type(pt_series: pd.Series) -> pd.Series:
    """
    Normalize property_type into ~10 standard categories.
    Unmatched types fall into 'Other'.
    """
    normalized = pt_series.str.lower().str.strip().map(PROPERTY_TYPE_MAP)
    return normalized.fillna("Other")


def parse_amenities(amenities_series: pd.Series) -> pd.Series:
    """
    Parse the amenities column from a JSON-like string into a list.

    Example:
        '["Wifi", "Kitchen", "Air conditioning"]' → ['Wifi', 'Kitchen', 'Air conditioning']
    """
    def _parse(val):
        if pd.isna(val) or val == "":
            return []
        try:
            # Handle both JSON array strings and bracket-enclosed strings
            val = str(val).strip()
            if val.startswith("["):
                return json.loads(val)
            return [v.strip().strip('"') for v in val.strip("{}").split(",") if v.strip()]
        except Exception:
            return []

    return amenities_series.apply(_parse)


def compute_amenity_flags(df: pd.DataFrame, amenity_col: str = "amenities_list") -> pd.DataFrame:
    """Create boolean flag columns for the most common amenities."""
    key_amenities = {
        "has_wifi":             ["Wifi", "Wireless Internet"],
        "has_kitchen":          ["Kitchen"],
        "has_parking":          ["Free parking on premises", "Paid parking on premises", "Parking"],
        "has_ac":               ["Air conditioning"],
        "has_washer":           ["Washer"],
        "has_tv":               ["TV", "Cable TV"],
        "has_elevator":         ["Elevator"],
        "has_pool":             ["Pool"],
        "has_gym":              ["Gym"],
        "has_hot_tub":          ["Hot tub"],
        "has_breakfast":        ["Breakfast"],
        "is_pet_friendly":      ["Pets allowed"],
        "has_long_term_stays":  ["Long term stays allowed"],
        "has_self_checkin":     ["Self check-in", "Keypad", "Lockbox", "Smart lock"],
    }

    if amenity_col not in df.columns:
        logger.warning(f"Column '{amenity_col}' not found. Skipping amenity flags.")
        return df

    for flag_name, keywords in key_amenities.items():
        df[flag_name] = df[amenity_col].apply(
            lambda lst: any(k.lower() in [a.lower() for a in lst] for k in keywords)
            if isinstance(lst, list) else False
        )

    return df


def load_gz_csv(file_path: str, **kwargs) -> pd.DataFrame:
    """Load a .gz compressed CSV file into a DataFrame."""
    logger.info(f"Loading: {file_path}")
    df = pd.read_csv(file_path, compression="gzip", low_memory=False, **kwargs)
    logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    return df


def save_parquet(df: pd.DataFrame, path: str, dataset_name: str = ""):
    """Save a DataFrame to Parquet format."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")
    size_mb = os.path.getsize(path) / (1024 * 1024)
    logger.success(f"Saved {dataset_name}: {path} ({len(df):,} rows, {size_mb:.2f} MB)")


# Listings cleaning

def clean_listings(bronze_dir: str, silver_dir: str, city_cfg: dict) -> pd.DataFrame:
    """Clean and standardize the listings dataset."""
    logger.info("─" * 50)
    logger.info("Cleaning: listings")

    # Find the listings file
    listings_file = os.path.join(bronze_dir, "listings_detailed_listings.csv.gz")
    if not os.path.exists(listings_file):
        listings_file = os.path.join(bronze_dir, "listings_listings.csv.gz")

    if not os.path.exists(listings_file):
        # Try to find any listings file
        candidates = [f for f in os.listdir(bronze_dir) if "listings" in f and f.endswith(".gz")]
        if candidates:
            listings_file = os.path.join(bronze_dir, candidates[0])
            logger.warning(f"Using fallback listings file: {candidates[0]}")
        else:
            raise FileNotFoundError(f"No listings file found in {bronze_dir}")

    df = load_gz_csv(listings_file)

    # ── Price columns ──────────────────────────────────────────
    for price_col in ["price", "weekly_price", "monthly_price", "security_deposit", "cleaning_fee"]:
        if price_col in df.columns:
            df[price_col] = parse_price(df[price_col])

    # ── Date columns ───────────────────────────────────────────
    for date_col in ["host_since", "last_review", "calendar_last_scraped", "first_review"]:
        if date_col in df.columns:
            df[date_col] = parse_date(df[date_col])

    # ── Room type normalization ────────────────────────────────
    if "room_type" in df.columns:
        df["room_type"] = normalize_room_type(df["room_type"])

    # ── Property type normalization ────────────────────────────
    if "property_type" in df.columns:
        df["property_type_std"] = normalize_property_type(df["property_type"])

    # ── Amenities ─────────────────────────────────────────────
    if "amenities" in df.columns:
        df["amenities_list"] = parse_amenities(df["amenities"])
        df["amenity_count"] = df["amenities_list"].apply(len)
        df = compute_amenity_flags(df)

    # ── Numeric casts ─────────────────────────────────────────
    for num_col in [
        "accommodates", "bedrooms", "beds", "bathrooms",
        "minimum_nights", "maximum_nights",
        "availability_30", "availability_60", "availability_90", "availability_365",
        "number_of_reviews", "number_of_reviews_ltm", "number_of_reviews_l30d",
        "calculated_host_listings_count",
        "reviews_per_month",
    ]:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    # ── Review scores ─────────────────────────────────────────
    for score_col in [
        "review_scores_rating", "review_scores_accuracy", "review_scores_cleanliness",
        "review_scores_checkin", "review_scores_communication", "review_scores_location",
        "review_scores_value",
    ]:
        if score_col in df.columns:
            df[score_col] = pd.to_numeric(df[score_col], errors="coerce")

    # ── Boolean columns ────────────────────────────────────────
    for bool_col in ["host_is_superhost", "host_identity_verified", "has_availability", "instant_bookable"]:
        if bool_col in df.columns:
            df[bool_col] = df[bool_col].map({"t": True, "f": False, True: True, False: False})

    # ── Derived fields ─────────────────────────────────────────
    today = pd.Timestamp.today().normalize()

    if "host_since" in df.columns:
        df["host_tenure_years"] = (
            (today - df["host_since"]).dt.days / 365.25
        ).round(2)

    if "last_review" in df.columns:
        df["days_since_last_review"] = (today - df["last_review"]).dt.days

    if "price" in df.columns and "bedrooms" in df.columns:
        df["price_per_bedroom"] = (df["price"] / df["bedrooms"].clip(lower=1)).round(2)

    # Classify host type
    if "calculated_host_listings_count" in df.columns:
        df["is_commercial_host"] = df["calculated_host_listings_count"] > 1

    # ── Null handling ──────────────────────────────────────────
    # review_scores: fill with NaN (not imputed — too many missing, imputation biases analysis)
    # price: NaN rows flagged as invalid — not imputed (price is the key variable)
    # bedrooms/bathrooms: fill 0 nulls with 1 (reasonable default for studios)
    for col in ["bedrooms", "beds"]:
        if col in df.columns:
            df[col] = df[col].fillna(1)
    if "bathrooms" in df.columns:
        df["bathrooms"] = df["bathrooms"].fillna(1.0)

    # ── Validation ─────────────────────────────────────────────
    bounds = city_cfg.get("bounds", {})
    validator = ListingValidator(city_bounds=bounds)
    df, val_report = validator.validate(df)
    print_validation_report(val_report, "listings")

    # ── Save full Silver (with flags) ──────────────────────────
    full_path = os.path.join(silver_dir, "listings_full.parquet")
    save_parquet(df, full_path, "listings_full (with flags)")

    # ── Save clean subset (is_valid=True only) ─────────────────
    df_clean = df[df.get("is_valid", pd.Series([True] * len(df), index=df.index))].copy()
    clean_path = os.path.join(silver_dir, "listings.parquet")
    save_parquet(df_clean, clean_path, "listings_clean")

    logger.info(f"Listings: {len(df):,} total → {len(df_clean):,} clean ({len(df_clean)/len(df)*100:.1f}%)")
    return df_clean


# Calendar cleaning

def clean_calendar(bronze_dir: str, silver_dir: str) -> pd.DataFrame:
    """Clean and standardize the calendar dataset."""
    logger.info("─" * 50)
    logger.info("Cleaning: calendar")

    calendar_file = os.path.join(bronze_dir, "calendar_calendar.csv.gz")
    if not os.path.exists(calendar_file):
        candidates = [f for f in os.listdir(bronze_dir) if "calendar" in f and f.endswith(".gz")]
        if candidates:
            calendar_file = os.path.join(bronze_dir, candidates[0])

    # Calendar is large — read in chunks to avoid memory issues
    logger.info("Reading calendar in chunks (large file)...")
    chunk_size = 500_000
    chunks = []

    for chunk in pd.read_csv(
        calendar_file,
        compression="gzip",
        low_memory=False,
        chunksize=chunk_size,
    ):
        # Date
        chunk["date"] = parse_date(chunk["date"])

        # Available flag
        chunk["available"] = chunk["available"].map({"t": True, "f": False})

        # Price columns
        for price_col in ["price", "adjusted_price"]:
            if price_col in chunk.columns:
                chunk[price_col] = parse_price(chunk[price_col])

        # numeric casts
        for num_col in ["minimum_nights", "maximum_nights"]:
            if num_col in chunk.columns:
                chunk[num_col] = pd.to_numeric(chunk[num_col], errors="coerce")

        # Weekend flag
        chunk["is_weekend"] = chunk["date"].dt.dayofweek >= 5
        chunk["day_of_week"] = chunk["date"].dt.day_name()
        chunk["month"] = chunk["date"].dt.month
        chunk["year"] = chunk["date"].dt.year

        chunks.append(chunk)
        logger.debug(f"  Processed chunk: {len(chunk):,} rows")

    df = pd.concat(chunks, ignore_index=True)
    logger.info(f"Calendar total: {len(df):,} rows")

    # Validate
    validator = CalendarValidator()
    df, val_report = validator.validate(df)
    print_validation_report(val_report, "calendar")

    # Save
    path = os.path.join(silver_dir, "calendar.parquet")
    save_parquet(df, path, "calendar")
    return df


# Reviews cleaning

def clean_reviews(bronze_dir: str, silver_dir: str) -> pd.DataFrame:
    """Clean and standardize the reviews dataset."""
    logger.info("─" * 50)
    logger.info("Cleaning: reviews")

    reviews_file = os.path.join(bronze_dir, "reviews_reviews.csv.gz")
    if not os.path.exists(reviews_file):
        candidates = [f for f in os.listdir(bronze_dir) if "reviews" in f and f.endswith(".gz")]
        if candidates:
            reviews_file = os.path.join(bronze_dir, candidates[0])

    df = load_gz_csv(reviews_file)

    # Date
    df["date"] = parse_date(df["date"])

    # Clean text
    if "comments" in df.columns:
        df["comments"] = df["comments"].astype(str).str.strip()
        df["comments"] = df["comments"].replace({"nan": None, "None": None})
        df["comment_length"] = df["comments"].str.len().fillna(0).astype(int)

    # Numeric casts
    for col in ["listing_id", "reviewer_id", "id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Deduplicate
    before = len(df)
    key_cols = [c for c in ["listing_id", "reviewer_id", "date"] if c in df.columns]
    df = df.drop_duplicates(subset=key_cols, keep="first")
    after = len(df)
    if before != after:
        logger.warning(f"Removed {before - after:,} duplicate reviews")

    # Save
    path = os.path.join(silver_dir, "reviews.parquet")
    save_parquet(df, path, "reviews")
    return df


# Neighbourhoods cleaning

def clean_neighbourhoods(bronze_dir: str, silver_dir: str) -> pd.DataFrame:
    """Load and clean the neighbourhoods CSV."""
    logger.info("─" * 50)
    logger.info("Cleaning: neighbourhoods")

    nb_file = os.path.join(bronze_dir, "neighbourhoods_csv_neighbourhoods.csv")
    if not os.path.exists(nb_file):
        candidates = [f for f in os.listdir(bronze_dir) if "neighbourhood" in f and f.endswith(".csv")]
        if candidates:
            nb_file = os.path.join(bronze_dir, candidates[0])
        else:
            logger.warning("No neighbourhoods CSV found. Skipping.")
            return pd.DataFrame()

    df = pd.read_csv(nb_file, encoding="utf-8")
    logger.info(f"Loaded {len(df):,} neighbourhood records")

    # Standardize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    path = os.path.join(silver_dir, "neighbourhoods.parquet")
    save_parquet(df, path, "neighbourhoods")
    return df


# Main orchestration

def run_silver_cleaning(
    city_name: str,
    config_path: str = "config/cities.yaml",
) -> dict:
    """Run all Silver layer cleaning steps for a given city."""
    logger.info("=" * 60)
    logger.info(f"SILVER CLEANING — {city_name.upper()}")
    logger.info("=" * 60)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    city_cfg = config["cities"][city_name]
    settings = config["settings"]
    bronze_dir = os.path.join(settings["raw_data_dir"], city_name)
    silver_dir = os.path.join(settings["silver_data_dir"], city_name)
    meta_db    = settings["metadata_db_path"]

    os.makedirs(silver_dir, exist_ok=True)
    meta = MetadataManager(meta_db)

    summary = {}

    # Listings
    try:
        import time
        t0 = time.time()
        df_listings = clean_listings(bronze_dir, silver_dir, city_cfg)
        duration = round(time.time() - t0, 2)
        meta.log_ingestion(city_name, "silver", "listings.parquet", "success",
                           file_path=os.path.join(silver_dir, "listings.parquet"),
                           row_count=len(df_listings), duration_sec=duration)
        summary["listings"] = {"rows": len(df_listings), "status": "success"}
    except Exception as e:
        logger.error(f"Listings cleaning failed: {e}")
        meta.log_ingestion(city_name, "silver", "listings.parquet", "failed", error_message=str(e))
        summary["listings"] = {"status": "failed", "error": str(e)}

    # Calendar
    try:
        t0 = time.time()
        df_cal = clean_calendar(bronze_dir, silver_dir)
        duration = round(time.time() - t0, 2)
        meta.log_ingestion(city_name, "silver", "calendar.parquet", "success",
                           file_path=os.path.join(silver_dir, "calendar.parquet"),
                           row_count=len(df_cal), duration_sec=duration)
        summary["calendar"] = {"rows": len(df_cal), "status": "success"}
    except Exception as e:
        logger.error(f"Calendar cleaning failed: {e}")
        meta.log_ingestion(city_name, "silver", "calendar.parquet", "failed", error_message=str(e))
        summary["calendar"] = {"status": "failed", "error": str(e)}

    # Reviews
    try:
        t0 = time.time()
        df_rev = clean_reviews(bronze_dir, silver_dir)
        duration = round(time.time() - t0, 2)
        meta.log_ingestion(city_name, "silver", "reviews.parquet", "success",
                           file_path=os.path.join(silver_dir, "reviews.parquet"),
                           row_count=len(df_rev), duration_sec=duration)
        summary["reviews"] = {"rows": len(df_rev), "status": "success"}
    except Exception as e:
        logger.error(f"Reviews cleaning failed: {e}")
        meta.log_ingestion(city_name, "silver", "reviews.parquet", "failed", error_message=str(e))
        summary["reviews"] = {"status": "failed", "error": str(e)}

    # Neighbourhoods
    try:
        t0 = time.time()
        df_nb = clean_neighbourhoods(bronze_dir, silver_dir)
        duration = round(time.time() - t0, 2)
        if len(df_nb) > 0:
            meta.log_ingestion(city_name, "silver", "neighbourhoods.parquet", "success",
                               file_path=os.path.join(silver_dir, "neighbourhoods.parquet"),
                               row_count=len(df_nb), duration_sec=duration)
        summary["neighbourhoods"] = {"rows": len(df_nb), "status": "success"}
    except Exception as e:
        logger.error(f"Neighbourhoods cleaning failed: {e}")
        summary["neighbourhoods"] = {"status": "failed", "error": str(e)}

    # Print final summary
    logger.info("\n" + "=" * 60)
    logger.info(f"SILVER CLEANING COMPLETE — {city_name.upper()}")
    for dataset, info in summary.items():
        if info.get("status") == "success":
            logger.success(f"  ✓ {dataset:<20} {info.get('rows', 0):>10,} rows")
        else:
            logger.error(f"  ✗ {dataset:<20} FAILED: {info.get('error', '')[:40]}")
    logger.info("=" * 60)

    meta.print_summary(city_name)
    return summary


# ──────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Silver Layer — Data Cleaning")
    parser.add_argument("--city", type=str, default="london")
    parser.add_argument("--config", type=str, default="config/cities.yaml")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    logger.add(
        f"logs/silver_{args.city}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="10 MB",
        level="DEBUG",
    )

    run_silver_cleaning(args.city, args.config)
