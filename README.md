# Airbnb Market Intelligence Pipeline
## London, England — Inside Airbnb Data Challenge

> Built with Medallion Architecture (Bronze → Silver → Gold)

---

## Architecture

```
Inside Airbnb (Source)
        │
        ▼
🟤 BRONZE LAYER          Raw .csv.gz files, downloaded as-is
        │
        ▼
🥈 SILVER LAYER          Cleaned Parquet files (standardized, validated, enriched)
        │
        ▼
🥇 GOLD LAYER            Star schema in DuckDB (fact + dimension tables via dbt)
        │
        ▼
📊 STREAMLIT DASHBOARD   Interactive market intelligence explorer
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12, SQL |
| Data Processing | pandas, pyarrow |
| Data Warehouse | DuckDB |
| Transformation | dbt-core + dbt-duckdb |
| Visualization | plotly, seaborn, Folium |
| Statistics | scipy, statsmodels |
| ML | scikit-learn, XGBoost, SHAP |
| Dashboard | Streamlit |
| Containerization | Docker + docker-compose |
| Testing | pytest |

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repo-url>
cd Airbnb_DataPipeline
```

### 2. Create a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Pipeline

### 1. Extract & Load (Bronze & Silver Layers)
The orchestrator downloads raw files (Bronze) and cleans them into Parquet format (Silver).
```bash
python pipeline/orchestrator.py --city london --phases all
```

### 2. Transform (Gold Layer via dbt)
Build the DuckDB star schema (fact and dimension tables) from the Silver Parquet files.
```bash
cd dbt_project
dbt deps
dbt run
cd ..
```

### 3. Machine Learning (Optional)
Train the XGBoost price prediction model (a pre-trained `.pkl` is already included).
```bash
python models/train_model.py
```

---

## Running Tests
```bash
pytest tests/ -v --tb=short
```

---

## Running the Dashboard
```bash
streamlit run dashboard/Home.py
```

---

## Running with Docker
```bash
docker-compose up --build
```

---

## Project Structure

```
Airbnb_DataPipeline/
├── config/
│   └── cities.yaml              City config & download URLs
├── data/
│   ├── bronze/london/           Raw downloaded files (gitignored)
│   ├── silver/london/           Cleaned Parquet files (gitignored)
│   └── gold/                    DuckDB star schema
├── pipeline/
│   ├── bronze_ingest.py         Download & validate raw files
│   ├── silver_clean.py          Clean, standardize, validate
│   ├── silver_enrich.py         Join & derive enriched fields
│   ├── gold_load.py             Load Silver into DuckDB
│   ├── profiler.py              Data quality profiling report
│   ├── validator.py             Domain rule validation
│   ├── metadata.py              Pipeline metadata & lineage tracking
│   └── orchestrator.py         End-to-end pipeline runner
├── dbt_project/                 dbt models for Gold layer
├── notebooks/                   Jupyter analysis notebooks
├── dashboard/                   Streamlit app
├── sql/                         Analytical SQL queries
├── tests/                       pytest unit tests
├── logs/                        Pipeline execution logs
├── reports/                     Data quality HTML reports
├── requirements.txt
├── docker-compose.yml
└── create_notebooks.py
```

---

## Execution Order

1. `pip install -r requirements.txt`
2. `python pipeline/orchestrator.py --city london --phases all`
3. `cd dbt_project && dbt run && cd ..`
4. `python models/train_model.py` *(Optional)*
5. `streamlit run dashboard/app.py`

