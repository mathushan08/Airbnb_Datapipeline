"""
Metadata management for tracking ingestion events, file statistics, and pipeline history.
"""

import duckdb
import os
from datetime import datetime
from loguru import logger


class MetadataManager:
    """
    Manages pipeline metadata stored in a lightweight DuckDB database.
    Records ingestion events, row counts, file sizes, and statuses.
    """

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._initialize_schema()

    def _initialize_schema(self):
        """Create metadata tables if they don't already exist."""
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_log (
                    log_id        INTEGER PRIMARY KEY,
                    city          VARCHAR NOT NULL,
                    layer         VARCHAR NOT NULL,        -- bronze | silver | gold
                    file_name     VARCHAR NOT NULL,
                    source_url    VARCHAR,
                    file_path     VARCHAR,
                    ingested_at   TIMESTAMP NOT NULL,
                    row_count     BIGINT,
                    file_size_mb  DOUBLE,
                    status        VARCHAR NOT NULL,        -- success | failed | skipped
                    error_message VARCHAR,
                    duration_sec  DOUBLE
                )
            """)

            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS ingestion_log_seq START 1
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id       INTEGER PRIMARY KEY,
                    city         VARCHAR NOT NULL,
                    started_at   TIMESTAMP NOT NULL,
                    finished_at  TIMESTAMP,
                    phases       VARCHAR,                  -- e.g. "bronze,silver"
                    status       VARCHAR NOT NULL,         -- running | success | failed
                    error_message VARCHAR
                )
            """)

            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS pipeline_runs_seq START 1
            """)
        logger.debug(f"Metadata schema initialized at: {self.db_path}")

    def log_ingestion(
        self,
        city: str,
        layer: str,
        file_name: str,
        status: str,
        source_url: str = None,
        file_path: str = None,
        row_count: int = None,
        file_size_mb: float = None,
        error_message: str = None,
        duration_sec: float = None,
    ):
        """Record a single file ingestion event."""
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ingestion_log (
                    log_id, city, layer, file_name, source_url, file_path,
                    ingested_at, row_count, file_size_mb, status,
                    error_message, duration_sec
                ) VALUES (
                    nextval('ingestion_log_seq'), ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?
                )
            """, [
                city, layer, file_name, source_url, file_path,
                datetime.now(), row_count, file_size_mb, status,
                error_message, duration_sec
            ])
        logger.debug(f"Logged ingestion: [{layer}] {file_name} → {status}")

    def start_pipeline_run(self, city: str, phases: list) -> int:
        """Record the start of a full pipeline run."""
        with duckdb.connect(self.db_path) as conn:
            result = conn.execute("""
                INSERT INTO pipeline_runs (run_id, city, started_at, phases, status)
                VALUES (nextval('pipeline_runs_seq'), ?, ?, ?, 'running')
                RETURNING run_id
            """, [city, datetime.now(), ",".join(phases)]).fetchone()
            run_id = result[0]
        logger.info(f"Pipeline run started: run_id={run_id}, city={city}, phases={phases}")
        return run_id

    def finish_pipeline_run(self, run_id: int, status: str, error_message: str = None):
        """Update a pipeline run as finished."""
        with duckdb.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE pipeline_runs
                SET finished_at = ?, status = ?, error_message = ?
                WHERE run_id = ?
            """, [datetime.now(), status, error_message, run_id])
        logger.info(f"Pipeline run {run_id} finished: {status}")

    def file_already_ingested(self, city: str, layer: str, file_name: str) -> bool:
        """Check if a file was already successfully ingested."""
        with duckdb.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT COUNT(*) FROM ingestion_log
                WHERE city = ? AND layer = ? AND file_name = ? AND status = 'success'
            """, [city, layer, file_name]).fetchone()
            return result[0] > 0

    def get_ingestion_summary(self, city: str = None) -> list:
        """Retrieve a summary of all ingestion events."""
        with duckdb.connect(self.db_path) as conn:
            if city:
                return conn.execute("""
                    SELECT city, layer, file_name, ingested_at, row_count,
                           file_size_mb, status, duration_sec
                    FROM ingestion_log
                    WHERE city = ?
                    ORDER BY ingested_at DESC
                """, [city]).fetchall()
            else:
                return conn.execute("""
                    SELECT city, layer, file_name, ingested_at, row_count,
                           file_size_mb, status, duration_sec
                    FROM ingestion_log
                    ORDER BY ingested_at DESC
                """).fetchall()

    def print_summary(self, city: str = None):
        """Print a formatted ingestion summary table."""
        records = self.get_ingestion_summary(city)
        if not records:
            logger.info("No ingestion records found.")
            return

        print("\n" + "=" * 90)
        print(f"{'CITY':<12} {'LAYER':<8} {'FILE':<30} {'ROWS':>10} {'MB':>6} {'STATUS':<10}")
        print("=" * 90)
        for r in records:
            city_n, layer, fname, ts, rows, mb, status, dur = r
            rows_str = f"{rows:,}" if rows else "N/A"
            mb_str = f"{mb:.1f}" if mb else "N/A"
            print(f"{city_n:<12} {layer:<8} {fname:<30} {rows_str:>10} {mb_str:>6} {status:<10}")
        print("=" * 90 + "\n")
