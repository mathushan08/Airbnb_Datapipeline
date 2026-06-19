"""
Bronze Layer — Raw Data Ingestion

Downloads all Inside Airbnb files for a given city and saves
them as-is into the Bronze layer (data/bronze/<city>/).
"""

import os
import time
import gzip
import shutil
import requests
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from loguru import logger

from pipeline.metadata import MetadataManager


# Configuration loader

def load_config(config_path: str = "config/cities.yaml") -> dict:
    """Load the city configuration from YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logger.info(f"Config loaded from: {config_path}")
    return config


def get_city_config(config: dict, city_name: str) -> dict:
    """Extract configuration for a specific city."""
    if city_name not in config["cities"]:
        available = list(config["cities"].keys())
        raise KeyError(
            f"City '{city_name}' not found in config. Available: {available}"
        )
    return config["cities"][city_name]


# Download utilities

def download_file(
    url: str,
    dest_path: str,
    max_retries: int = 3,
    retry_delay: int = 5,
) -> float:
    """Download a file from a URL with retry logic and progress bar."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # Browser-like headers to avoid 403 Forbidden from Inside Airbnb CDN
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://insideairbnb.com/get-the-data/",
        "Connection": "keep-alive",
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Attempt {attempt}/{max_retries}] Downloading: {url}")
            response = requests.get(url, stream=True, timeout=180, headers=headers)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            file_name = os.path.basename(dest_path)

            with open(dest_path, "wb") as f, tqdm(
                desc=f"  {file_name}",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                ncols=80,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))

            file_size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            logger.success(f"Downloaded: {file_name} ({file_size_mb:.2f} MB)")
            return file_size_mb

        except (requests.RequestException, IOError) as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                wait = retry_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"All {max_retries} attempts failed for URL: {url}"
                ) from e


def count_rows_gz(file_path: str) -> int:
    """Count the number of data rows in a .gz CSV file."""
    try:
        with gzip.open(file_path, "rt", encoding="utf-8", errors="replace") as f:
            # Subtract 1 for the header row
            return sum(1 for _ in f) - 1
    except Exception as e:
        logger.warning(f"Could not count rows in {file_path}: {e}")
        return -1


def count_rows_csv(file_path: str) -> int:
    """Count rows in a plain CSV file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f) - 1
    except Exception as e:
        logger.warning(f"Could not count rows in {file_path}: {e}")
        return -1


def validate_downloaded_file(file_path: str) -> bool:
    """Validate that a downloaded file exists and is non-empty."""
    if not os.path.exists(file_path):
        logger.error(f"File not found after download: {file_path}")
        return False
    if os.path.getsize(file_path) == 0:
        logger.error(f"File is empty: {file_path}")
        return False
    return True


# Main ingestion logic

def ingest_bronze_city(
    city_name: str,
    config_path: str = "config/cities.yaml",
    force: bool = False,
) -> dict:
    """Download all Inside Airbnb files for a city into the Bronze layer."""
    logger.info("=" * 60)
    logger.info(f"BRONZE INGESTION — {city_name.upper()}")
    logger.info("=" * 60)

    # Load config
    config = load_config(config_path)
    city_cfg = get_city_config(config, city_name)
    settings = config["settings"]

    # Setup paths
    bronze_dir = os.path.join(settings["raw_data_dir"], city_name)
    meta_db = settings["metadata_db_path"]
    os.makedirs(bronze_dir, exist_ok=True)
    os.makedirs(os.path.dirname(meta_db), exist_ok=True)

    meta = MetadataManager(meta_db)
    run_id = meta.start_pipeline_run(city_name, ["bronze"])

    base_url = city_cfg["base_url"]
    files_cfg = city_cfg["files"]
    max_retries = settings.get("max_retries", 3)
    retry_delay = settings.get("retry_delay_seconds", 5)

    summary = {"city": city_name, "files": {}, "total_files": 0, "success": 0, "failed": 0, "skipped": 0}

    # Build file download list
    download_tasks = []
    for file_key, file_value in files_cfg.items():
        # Some files may be full URLs (neighbourhoods), others are just filenames
        if file_value.startswith("http"):
            url = file_value
        else:
            url = base_url + file_value

        # Determine local filename
        local_name = file_key + "_" + os.path.basename(file_value)
        dest_path = os.path.join(bronze_dir, local_name)
        download_tasks.append((file_key, url, dest_path, local_name))

    summary["total_files"] = len(download_tasks)

    for file_key, url, dest_path, local_name in download_tasks:
        start_time = time.time()

        # Incremental check — skip if already ingested and not forced
        if not force and meta.file_already_ingested(city_name, "bronze", local_name):
            logger.info(f"[SKIP] Already ingested: {local_name} (use --force to re-download)")
            summary["skipped"] += 1
            summary["files"][file_key] = {"status": "skipped", "file": local_name}
            meta.log_ingestion(city=city_name, layer="bronze", file_name=local_name, status="skipped")
            continue

        try:
            # Download
            file_size_mb = download_file(url, dest_path, max_retries, retry_delay)

            # Validate
            if not validate_downloaded_file(dest_path):
                raise ValueError(f"Validation failed for {local_name}")

            # Count rows
            if local_name.endswith(".gz"):
                row_count = count_rows_gz(dest_path)
            elif local_name.endswith(".csv"):
                row_count = count_rows_csv(dest_path)
            else:
                row_count = None  # GeoJSON etc.

            duration = round(time.time() - start_time, 2)

            # Log success
            meta.log_ingestion(
                city=city_name,
                layer="bronze",
                file_name=local_name,
                status="success",
                source_url=url,
                file_path=dest_path,
                row_count=row_count,
                file_size_mb=round(file_size_mb, 2),
                duration_sec=duration,
            )

            summary["success"] += 1
            summary["files"][file_key] = {
                "status": "success",
                "file": local_name,
                "path": dest_path,
                "rows": row_count,
                "size_mb": round(file_size_mb, 2),
                "duration_sec": duration,
            }

            row_str = f"{row_count:,}" if row_count and row_count >= 0 else "N/A"
            logger.success(
                f"[OK] {local_name} | rows={row_str} | "
                f"size={file_size_mb:.2f}MB | time={duration}s"
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            logger.error(f"[FAIL] {local_name}: {e}")
            meta.log_ingestion(
                city=city_name,
                layer="bronze",
                file_name=local_name,
                status="failed",
                source_url=url,
                error_message=str(e),
                duration_sec=duration,
            )
            summary["failed"] += 1
            summary["files"][file_key] = {"status": "failed", "file": local_name, "error": str(e)}

    # Finalize run
    final_status = "success" if summary["failed"] == 0 else "failed"
    meta.finish_pipeline_run(run_id, final_status)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info(f"BRONZE INGESTION COMPLETE — {city_name.upper()}")
    logger.info(f"  Total:   {summary['total_files']}")
    logger.info(f"  Success: {summary['success']}")
    logger.info(f"  Skipped: {summary['skipped']}")
    logger.info(f"  Failed:  {summary['failed']}")
    logger.info("=" * 60)

    meta.print_summary(city_name)

    return summary


# ──────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bronze Layer — Inside Airbnb Ingestion")
    parser.add_argument("--city", type=str, default="london", help="City name from config")
    parser.add_argument("--config", type=str, default="config/cities.yaml", help="Config file path")
    parser.add_argument("--force", action="store_true", help="Re-download even if already ingested")
    args = parser.parse_args()

    # Setup logging
    os.makedirs("logs", exist_ok=True)
    logger.add(
        f"logs/bronze_{args.city}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="10 MB",
        level="DEBUG",
    )

    result = ingest_bronze_city(args.city, args.config, args.force)
