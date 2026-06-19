"""
Domain Validation Rules for the Airbnb Data Pipeline.

Applies business-rule validation to cleaned DataFrames and
produces a validation report showing which records failed
which rules, with counts and percentages.
"""

import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict, Tuple


# Validation rule definitions

class ListingValidator:
    """Validates cleaned listings DataFrame against domain rules."""

    def __init__(self, city_bounds: dict):
        self.bounds = city_bounds

    def validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """Run all validation rules and add flag columns."""
        df = df.copy()
        total = len(df)
        report = {"total_records": total, "rules": {}}

        # Rule 1: Price must be positive
        if "price" in df.columns:
            mask = df["price"].notna() & (df["price"] > 0)
            df["flag_valid_price"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_price"] = {
                "description": "price > 0",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 2: Latitude must be within city bounds
        if "latitude" in df.columns:
            mask = (
                df["latitude"].notna()
                & df["latitude"].between(self.bounds["lat_min"], self.bounds["lat_max"])
            )
            df["flag_valid_lat"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_latitude"] = {
                "description": f"lat ∈ [{self.bounds['lat_min']}, {self.bounds['lat_max']}]",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 3: Longitude must be within city bounds
        if "longitude" in df.columns:
            mask = (
                df["longitude"].notna()
                & df["longitude"].between(self.bounds["lon_min"], self.bounds["lon_max"])
            )
            df["flag_valid_lon"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_longitude"] = {
                "description": f"lon ∈ [{self.bounds['lon_min']}, {self.bounds['lon_max']}]",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 4: minimum_nights must be between 1 and 365
        if "minimum_nights" in df.columns:
            mask = (
                df["minimum_nights"].notna()
                & df["minimum_nights"].between(1, 1125)  # 3 years max
            )
            df["flag_valid_min_nights"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_minimum_nights"] = {
                "description": "minimum_nights ∈ [1, 1125]",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 5: availability_365 must be 0–365
        if "availability_365" in df.columns:
            mask = (
                df["availability_365"].notna()
                & df["availability_365"].between(0, 365)
            )
            df["flag_valid_availability"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_availability"] = {
                "description": "availability_365 ∈ [0, 365]",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 6: review_scores_rating must be 0–5 (if present)
        if "review_scores_rating" in df.columns:
            non_null = df["review_scores_rating"].notna()
            mask = ~non_null | df["review_scores_rating"].between(0, 5)
            df["flag_valid_rating"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_review_rating"] = {
                "description": "review_scores_rating ∈ [0, 5] (when not null)",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Rule 7: listing_id must be non-null and unique
        if "id" in df.columns:
            mask = df["id"].notna()
            df["flag_valid_id"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_listing_id"] = {
                "description": "listing id is not null",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }
            dup_count = df["id"].duplicated().sum()
            report["rules"]["unique_listing_id"] = {
                "description": "listing id is unique",
                "failed": int(dup_count),
                "pct_failed": round(dup_count / total * 100, 2),
            }

        # Rule 8: host_since must not be in the future
        if "host_since" in df.columns:
            today = pd.Timestamp.today().normalize()
            non_null = df["host_since"].notna()
            mask = ~non_null | (df["host_since"] <= today)
            df["flag_valid_host_since"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_host_since"] = {
                "description": "host_since <= today",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Composite: is the record fully valid?
        flag_cols = [c for c in df.columns if c.startswith("flag_valid")]
        if flag_cols:
            df["is_valid"] = df[flag_cols].all(axis=1)
            invalid_total = (~df["is_valid"]).sum()
            report["total_invalid"] = int(invalid_total)
            report["total_valid"] = int(total - invalid_total)
            report["pct_valid"] = round((total - invalid_total) / total * 100, 2)

        return df, report


class CalendarValidator:
    """Validates the calendar DataFrame."""

    def validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        df = df.copy()
        total = len(df)
        report = {"total_records": total, "rules": {}}

        # Price must be positive when not null
        if "price" in df.columns:
            non_null = df["price"].notna()
            mask = ~non_null | (df["price"] > 0)
            df["flag_valid_price"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_price"] = {
                "description": "price > 0 (when not null)",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        # Available must be boolean (t/f already converted)
        if "available" in df.columns:
            mask = df["available"].isin([True, False])
            df["flag_valid_available"] = mask
            fails = (~mask).sum()
            report["rules"]["valid_available"] = {
                "description": "available is boolean",
                "failed": int(fails),
                "pct_failed": round(fails / total * 100, 2),
            }

        flag_cols = [c for c in df.columns if c.startswith("flag_valid")]
        if flag_cols:
            df["is_valid"] = df[flag_cols].all(axis=1)
            invalid_total = (~df["is_valid"]).sum()
            report["total_invalid"] = int(invalid_total)
            report["total_valid"] = int(total - invalid_total)
            report["pct_valid"] = round((total - invalid_total) / total * 100, 2)

        return df, report


# Report printer

def print_validation_report(report: dict, dataset_name: str = "listings"):
    """Pretty-print a validation report to the console."""
    print(f"\n{'=' * 60}")
    print(f"  VALIDATION REPORT — {dataset_name.upper()}")
    print(f"{'=' * 60}")
    print(f"  Total records: {report.get('total_records', 'N/A'):,}")
    print(f"  Valid records: {report.get('total_valid', 'N/A'):,} ({report.get('pct_valid', 'N/A')}%)")
    print(f"  Invalid:       {report.get('total_invalid', 'N/A'):,}")
    print(f"\n  Rule-level breakdown:")
    print(f"  {'Rule':<35} {'Failed':>10} {'% Failed':>10}")
    print(f"  {'-' * 57}")
    for rule, stats in report.get("rules", {}).items():
        print(
            f"  {rule:<35} {stats['failed']:>10,} {stats['pct_failed']:>9.2f}%"
        )
    print(f"{'=' * 60}\n")
