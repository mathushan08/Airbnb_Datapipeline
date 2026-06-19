# Data Directory

This directory contains all pipeline data organized by Medallion layer.

## Structure

```
data/
├── bronze/          # Raw downloaded files from Inside Airbnb (.csv.gz, .geojson)
│   └── london/
├── silver/          # Cleaned, validated, enriched Parquet files
│   └── london/
└── gold/            # DuckDB star schema database
    └── airbnb_london.duckdb
```

## Important

- `bronze/` and `silver/` directories are **gitignored** — data files are not committed.
- Run `python pipeline/orchestrator.py --city london --phases all` to regenerate.
- See `README.md` for full setup instructions.
