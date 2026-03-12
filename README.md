# Fake Store API — End-to-End Data Pipeline

I built this project to demonstrate a complete data pipeline — from raw API data all the way to a live dashboard. It pulls product, user, and shopping cart data from [fakestoreapi.com](https://fakestoreapi.com), lands it in S3, loads it into Snowflake, transforms it with dbt, and visualises the results in a Streamlit dashboard. Airflow orchestrates the whole thing daily using Docker Compose.

## Pipeline overview

```
FakeStoreAPI → Python → S3 → Snowflake → dbt → Streamlit
                                              └→ Snowflake ML (Classification)
```

Here's what each step does:

1. **Fetch** — a Python script calls the API and saves the responses as timestamped JSON files locally
2. **Upload** — another script pushes those files to an S3 bucket, organised by endpoint (`products/`, `users/`, `carts/`)
3. **Load** — Snowflake's `COPY INTO` reads from an external S3 stage and loads the raw JSON into VARIANT tables
4. **Transform** — dbt builds staging views (parse JSON → typed columns), business tables (joins, aggregations), and an ML feature table
5. **Dashboard** — Streamlit connects to the business tables and shows live metrics
6. **ML** — Snowflake Cortex ML trains a classification model to predict which product category each user prefers
7. **Orchestrate** — Airflow runs steps 1–4 in sequence every day at midnight UTC

## Project structure

```
fakestoreapi-pipeline/
│
├── scripts/
│   ├── fetch_data.py              # pulls data from the API
│   ├── upload_to_s3.py            # pushes raw JSON to S3
│   └── load_to_snowflake.py       # COPY INTO from S3 → Snowflake
│
├── snowflake/
│   ├── 01_setup.sql               # roles, warehouse, database, schemas
│   ├── 02_raw_tables_and_stage.sql # external stage + raw VARIANT tables
│   └── 03_ml_model.sql            # Cortex ML classification model + predictions
│
├── dbt_project/
│   ├── models/
│   │   ├── 01_staging/            # stg_products, stg_users, stg_carts
│   │   ├── 02_standardization/    # (reserved for future use)
│   │   ├── 03_business/           # order_items, user_purchase_summary, revenue_by_category
│   │   └── 04_ml_features/        # user_features (input for the ML model)
│   ├── dbt_project.yml
│   └── profiles.yml
│
├── streamlit/
│   └── dashboard.py               # analytics dashboard (4 sections)
│
├── airflow/
│   └── dags/
│       └── fakestore_pipeline.py  # DAG with 5 tasks
│
├── docker/
│   └── Dockerfile                 # Airflow image + Python dependencies
│
├── infra/
│   └── architecture.md            # architecture diagram + design decisions
│
├── docker-compose.yml             # spins up Airflow (postgres + webserver + scheduler)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Getting started

### Prerequisites

- Python 3.11+
- A Snowflake account (free trial works fine)
- An AWS account with an S3 bucket
- Docker Desktop (for Airflow)

### 1. Clone and set up credentials

```bash
git clone <repo-url>
cd fakestoreapi-pipeline

python -m venv .venv
source .venv/Scripts/activate   # Windows
pip install -r requirements.txt

cp .env.example .env
# fill in your Snowflake and AWS credentials
```

### 2. Set up Snowflake

Open a Snowflake worksheet and run these in order:

```
snowflake/01_setup.sql          # creates FAKESTORE_ROLE, FAKESTORE_WH, FAKESTORE_DB
snowflake/02_raw_tables_and_stage.sql   # creates the S3 stage and raw tables
```

### 3. Run the pipeline manually

```bash
python scripts/fetch_data.py
python scripts/upload_to_s3.py
python scripts/load_to_snowflake.py

cd dbt_project
dbt run --profiles-dir .
dbt test --profiles-dir .
```

### 4. Start the dashboard

```bash
streamlit run streamlit/dashboard.py
```

### 5. Or let Airflow handle it

```bash
docker compose up -d
# open http://localhost:8080
# login: airflow / airflow
# trigger the fakestore_pipeline DAG
```

Airflow runs 5 tasks in order: `fetch_data → upload_to_s3 → load_to_snowflake → dbt_run → dbt_test`. If any step fails, the rest don't execute — existing data stays safe.

### 6. (Optional) Train the ML model

After dbt has built the `ML.USER_FEATURES` table, create a Snowflake Cortex ML Classification model using the Snowflake UI (AI & ML → Studio → Classification). Then run the prediction queries in `snowflake/03_ml_model.sql`.

## Data model

```
RAW (VARIANT — raw JSON as-is)
 │
 └─► STAGING (views — parse JSON into typed columns)
      ├── stg_products    → product_id, title, price, category, rating
      ├── stg_users       → user_id, name, email, city, geo coordinates
      └── stg_carts       → cart_id, user_id, product_id, quantity, date
           │
           └─► BUSINESS (tables — joins + aggregations)
                ├── order_items            → one row per item per cart, with revenue
                ├── user_purchase_summary  → one row per user, total spend, favourite category
                └── revenue_by_category    → category-level revenue and customer metrics
                     │
                     └─► ML
                          ├── user_features             → feature table for classification
                          └── user_interest_predictions  → predicted vs actual category
```

## Testing

dbt runs 22 tests total:

- **Schema tests** — `unique` and `not_null` on key columns across all models
- **Unit tests** — mock data tests for `order_items`, `user_purchase_summary`, and `user_features` to validate join logic

```bash
cd dbt_project && dbt test --profiles-dir .
```

## Tech choices

| Layer | Tool | Reasoning |
|-------|------|-----------|
| Extract | Python + requests | the API is simple REST — no need for a heavy framework |
| Storage | AWS S3 | cheap, scalable, doubles as Snowflake external stage |
| Warehouse | Snowflake | handles JSON natively with VARIANT, separates compute from storage |
| Transform | dbt | SQL-based, testable, tracks dependencies and lineage automatically |
| Dashboard | Streamlit | python-native, fast to build, connects directly to Snowflake |
| ML | Snowflake Cortex | everything stays inside Snowflake — no external ML infrastructure |
| Orchestrate | Airflow | industry standard, clear task dependencies, retry logic built in |
| Containerize | Docker Compose | one command spins up Airflow locally with Postgres |

## What I'd change for production

| Area | Current | Production |
|------|---------|------------|
| Secrets | `.env` file | AWS Secrets Manager or Snowflake key-pair auth |
| Airflow | Docker Compose, LocalExecutor | AWS MWAA or Kubernetes + CeleryExecutor |
| Monitoring | none | Slack alerts on failure, dbt test reports, Snowflake query history |
| CI/CD | manual | GitHub Actions — lint, test, deploy dbt, trigger DAG |
| Environments | single database | separate dev / staging / prod with dbt targets |
| Data quality | dbt schema tests | + Great Expectations, row count monitoring, freshness checks |
| Loading | full load (truncate + copy) | incremental with MERGE or Snowpipe |

## Dashboard

The Streamlit dashboard has 4 sections:

1. **Overview** — total customers, orders, revenue, items sold
2. **Revenue by Category** — bar chart + table with category breakdown
3. **Top Customers** — ranked by total spend with favourite category
4. **ML Predictions** — predicted user interests from the Cortex classification model (shows when available, gracefully hidden otherwise)
