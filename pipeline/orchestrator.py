"""
Pipeline Orchestrator — End-to-End Runner

Runs the full Medallion pipeline (Bronze → Silver → Gold) for a
given city. Each phase can be run independently or together.
"""

import os
import sys

# Ensure the project root is on the Python path regardless of where the script is run from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
import argparse
from datetime import datetime
from loguru import logger

# Fix Windows console encoding for unicode characters
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def setup_logging(city: str):
    """Configure loguru for console + file output."""
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/pipeline_{city}_{timestamp}.log"

    # Remove default handler, add custom ones
    logger.remove()
    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
    logger.add(
        utf8_stdout,
        format="{time:HH:mm:ss} | {level: <8} | {message}",
        level="INFO",
        colorize=False,
    )
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="50 MB",
    )
    logger.info(f"Logging to: {log_file}")


def run_pipeline(city: str, phases: list, config_path: str, force: bool = False):
    """Run the specified pipeline phases for a city."""
    setup_logging(city)

    logger.info("=" * 56)
    logger.info(f"  AIRBNB MEDALLION PIPELINE -- {city.upper()}")
    logger.info("=" * 56)
    logger.info(f"Phases to run: {phases}")
    logger.info(f"Config: {config_path}")
    logger.info(f"Force re-download: {force}")

    pipeline_start = time.time()
    results = {}

    # Phase 1: Bronze
    if "bronze" in phases:
        logger.info("\n" + "▶ " * 20)
        logger.info("▶  PHASE 1: BRONZE — Raw Data Ingestion")
        logger.info("▶ " * 20)
        t0 = time.time()
        try:
            from pipeline.bronze_ingest import ingest_bronze_city
            result = ingest_bronze_city(city, config_path, force=force)
            duration = round(time.time() - t0, 1)
            results["bronze"] = {"status": "success", "duration_sec": duration, "detail": result}
            logger.success(f"Bronze completed in {duration}s")
        except Exception as e:
            logger.error(f"Bronze phase failed: {e}")
            results["bronze"] = {"status": "failed", "error": str(e)}
            if "silver" in phases or "gold" in phases:
                logger.warning("Subsequent phases may fail without bronze data.")

    # Phase 2: Silver
    if "silver" in phases:
        logger.info("\n" + "▶ " * 20)
        logger.info("▶  PHASE 2: SILVER — Cleaning & Standardization")
        logger.info("▶ " * 20)
        t0 = time.time()
        try:
            from pipeline.silver_clean import run_silver_cleaning
            result = run_silver_cleaning(city, config_path)
            duration = round(time.time() - t0, 1)
            results["silver"] = {"status": "success", "duration_sec": duration, "detail": result}
            logger.success(f"Silver completed in {duration}s")
        except Exception as e:
            logger.error(f"Silver phase failed: {e}")
            results["silver"] = {"status": "failed", "error": str(e)}

    # Final Summary
    total_duration = round(time.time() - pipeline_start, 1)
    logger.info("\n" + "=" * 56)
    logger.info("  PIPELINE EXECUTION SUMMARY")
    logger.info("=" * 56)
    for phase, result in results.items():
        status_icon = "OK" if result["status"] == "success" else "FAIL"
        dur = result.get("duration_sec", "N/A")
        logger.info(f"  [{status_icon}] {phase.upper():<10} {result['status']:<10} {str(dur)+'s':>8}")
    logger.info("-" * 56)
    logger.info(f"  Total time: {total_duration}s")
    logger.info("=" * 56)

    return results


# CLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Airbnb Medallion Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Run full pipeline:
    python pipeline/orchestrator.py --city london --phases all

  Run only bronze ingestion:
    python pipeline/orchestrator.py --city london --phases bronze

  Run bronze + silver:
    python pipeline/orchestrator.py --city london --phases bronze silver

  Force re-download of bronze files:
    python pipeline/orchestrator.py --city london --phases bronze --force
        """,
    )
    parser.add_argument("--city", type=str, default="london", help="City key from config")
    parser.add_argument(
        "--phases",
        nargs="+",
        default=["all"],
        choices=["all", "bronze", "silver", "gold"],
        help="Pipeline phases to run",
    )
    parser.add_argument("--config", type=str, default="config/cities.yaml", help="Config file path")
    parser.add_argument("--force", action="store_true", help="Force re-download of bronze files")

    args = parser.parse_args()

    phases = ["bronze", "silver"] if "all" in args.phases else args.phases

    run_pipeline(args.city, phases, args.config, args.force)
