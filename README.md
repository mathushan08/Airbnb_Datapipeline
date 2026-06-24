# Airbnb Market Intelligence: London

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=for-the-badge&logo=dbt&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)

## Project Overview

This project is an end-to-end data engineering and machine learning platform built to analyze the short-term rental market in London using the **Inside Airbnb** dataset. The platform transforms raw, semi-structured data into actionable business intelligence for real estate investors and property managers. 

By leveraging a robust **Medallion Data Architecture (Bronze → Silver → Gold)**, the pipeline automates the extraction of raw files, applies strict data cleaning policies via Pandas, and models the data into a high-performance DuckDB Star Schema using `dbt`. Finally, an embedded XGBoost machine learning model predicts nightly rental prices, and the entire ecosystem is surfaced via an interactive Streamlit dashboard.

---

## 🎥 Dashboard Demo Video
Watch the interactive Streamlit dashboard in action, featuring Geospatial Heatmaps, an Investment Estimator, and a live AI Price Advisor:
👉 **[View the Demo Video on Google Drive](https://drive.google.com/file/d/1somSjs8itIbyZCylmAMAus-ek15wfUD7/view?usp=drive_link)**

---

## 🏗 Data Architecture

The pipeline follows a strict Medallion architecture pattern. Raw CSVs are ingested into the **Bronze** layer. They are subsequently cleaned, standardized, and saved as highly-compressed Parquet files in the **Silver** layer. Finally, DuckDB and dbt transform the Parquet files into a dimensional Star Schema in the **Gold** layer.

![Data Architecture Diagram](architecture.png)

---

## 🧬 dbt Lineage Graph

The Gold layer is orchestrated exclusively by `dbt`. The lineage graph below illustrates how the flat Silver-layer Parquet tables (Sources) are mapped into lightweight `stg_` views (Staging), and then joined into the final `dim_` and `fact_` tables (Marts) that power the dashboard.

![dbt Lineage Graph](lineage.png)
* **Green (Sources):** Raw inputs dynamically pointing to the Silver Parquet data.
* **Blue (Staging):** Type casting, renaming, and null handling.
* **Yellow (Marts):** Heavily joined Star Schema tables optimized for BI reads.

---

## 🚀 Setup & Execution (Docker)

The absolute easiest way to run the entire pipeline and dashboard is via Docker. This guarantees that all system dependencies, database drivers, and Python libraries run exactly as intended.

### Prerequisites
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ensure the Docker daemon is running).
- Git installed on your local machine.

### Step-by-Step Instructions

**1. Clone the repository:**
```bash
git clone <repository_url>
cd Airbnb_DataPipeline
```

**2. Build and run the containerized application:**
This single command will build the Docker image, install all requirements, run the Python orchestrator (downloading & cleaning data), execute the `dbt` models to build the DuckDB database, and finally launch the Streamlit dashboard on port `8501`.

```bash
docker-compose up --build
```
*(Note: The initial run may take a few minutes as it downloads the ~1GB dataset from Inside Airbnb and executes the pipeline).*

**3. Access the Dashboard:**
Once the terminal logs indicate that Streamlit is running, open your web browser and navigate to:
👉 **[http://localhost:8501](http://localhost:8501)**

**4. Shutting down:**
To cleanly stop the dashboard and container, simply press `Ctrl+C` in your terminal and then run:
```bash
docker-compose down
```

---

## 🛠 Manual Execution (Without Docker)

If you prefer to run the pipeline manually on your local machine without Docker, follow these steps:

1. **Setup Python Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run the Ingestion & Cleaning Pipeline (Bronze & Silver):**
   ```bash
   python pipeline/orchestrator.py --city london --phases all
   ```

3. **Run the dbt Transformations (Gold):**
   ```bash
   cd dbt_project
   dbt deps
   dbt run
   cd ..
   ```

4. **Launch the Dashboard:**
   ```bash
   streamlit run dashboard/Home.py
   ```

---

## 📁 Project Structure

```text
Airbnb_DataPipeline/
├── dashboard/               # Streamlit UI pages and custom styling (CSS)
├── data/                    # Local storage (Bronze CSVs, Silver Parquets, Gold DuckDB)
├── dbt_project/             # SQL transformations, macros, and schema definitions
├── pipeline/                # Python scripts for Bronze ingestion & Silver cleaning
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container blueprint
├── docker-compose.yml       # Orchestrates the container lifecycle
```
