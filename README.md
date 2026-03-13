# Fake Store API — Data Pipeline

A data pipeline that pulls from the [Fake Store API](https://fakestoreapi.com), lands JSON in S3, transforms it in Snowflake using dbt (reading directly from S3 via external stage), and shows the results in a Streamlit dashboard. 

The whole thing runs locally with Docker (Airflow orchestration) and connects to real AWS + Snowflake accounts.

---

## What it does

### Fetch

Three endpoints are pulled via Python `requests`:

- `/products` — 20 products with prices, categories, ratings
- `/users` — 10 users with names, addresses, geo-coordinates
- `/carts` — 7 carts (each cart has a list of product IDs and quantities)

The script (`scripts/fetch_data.py`) saves each as a timestamped JSON file under `data/raw/`. Nothing is filtered or changed at this stage — it's a raw dump.

### Store

`scripts/upload_to_s3.py` pushes those JSON files to an S3 bucket, organized like:

```
s3://schibsted-case-raw-data/raw/products/products_20260312_120000.json
s3://schibsted-case-raw-data/raw/users/users_20260312_120000.json
s3://schibsted-case-raw-data/raw/carts/carts_20260312_120000.json
```

S3 acts as the landing zone and source of truth for raw data. Snowflake reads from it directly through an external stage (`@S3_RAW_STAGE`), so dbt can query the JSON files without any intermediate load step.

### Transform (dbt)

This is where the data becomes useful. dbt runs 7 models across 4 layers:

**Staging** — Parse the JSON and flatten it into typed columns. One model per source entity.
- `stg_products` — reads directly from S3 stage, extracts product fields, deduplicates by product_id
- `stg_users` — same pattern, extracts names, address, geo coords
- `stg_carts` — flattens the nested `products` array so each row is one (cart, product) pair

**Standardization** — Reserved for cleaning/normalization (currently empty, but the layer exists for when it's needed).

**Business** — The  analytics layer.
- `order_items` — joins carts with products to get one row per purchased item, with price and revenue calculated
- `user_purchase_summary` — one row per user: total spend, order count, favorite category, first/last order date
- `revenue_by_category` — category-level metrics: revenue, customer count, avg price, items sold

**ML Features** — `user_features` combines purchase behavior with location data (city) into a feature table. This was built to feed Snowflake Cortex ML Classification, though the model couldn't be run (discussed below).

### Dashboard

A Streamlit app (`streamlit/dashboard.py`) that reads directly from the Snowflake `BUSINESS` schema. Four sections:

1. **Overview** — headline numbers (customers, orders, revenue, items)
2. **Revenue by Category** — bar chart + detail table
3. **Top Customers** — who's spending the most, what do they buy
4. **ML Predictions** — shows predicted user interests if the ML model has been created (gracefully falls back if not)

### Testing

23 tests total:
- **20 data tests** — not_null, unique constraints on key columns across all models (defined in `schema.yml` files)
- **3 unit tests** — `order_items` revenue calculation, `revenue_by_category` aggregation logic, and a custom test that checks each cart belongs to exactly one user
- All pass. Run them with `dbt test`.

---

## How to run it

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- A Snowflake account (free trial works)
- An AWS account with S3 access

### Setup

1. Clone the repo and create a virtualenv:

```bash
git clone https://github.com/suman373-code/Schibsted.git
cd fakestoreapi-pipeline
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

You need: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

3. Run the Snowflake setup scripts (once, as ACCOUNTADMIN):

```sql
-- Run snowflake/01_setup.sql first (creates role, warehouse, database, schemas)
-- Then snowflake/02_raw_tables_and_stage.sql (creates raw tables + S3 stage)
```

4. Run the pipeline manually:

```bash
python scripts/fetch_data.py
python scripts/upload_to_s3.py
```

5. Run dbt:

```bash
cd dbt_project
set -a && source ../.env && set +a    # load env vars for Snowflake
dbt run --profiles-dir .
dbt test --profiles-dir .
```

6. Start the dashboard:

```bash
streamlit run streamlit/dashboard.py
```

### Or just use Docker (Airflow)

```bash
docker-compose up -d
```

This starts Airflow at `http://localhost:8080` with a DAG (`fakestore_pipeline`) that runs 4 steps in order: fetch → upload to S3 → dbt run → dbt test. Trigger it manually from the UI or let it run on its daily schedule.

---

## Assumptions and shortcuts

A few things I'd do differently if this were a real production system:

- **Credentials live in a `.env` file.** In production, these would be in AWS Secrets Manager or Snowflake key-pair auth. 
- **Full refresh every run.** dbt reads all files from the S3 stage each time. With 20 products and 10 users, there's no point in incremental logic. At scale, I'd switch to incremental models in dbt and use S3 date partitions.
- **No CI/CD.** Right now you run dbt locally or through Airflow. In production, I'd have GitHub Actions running `dbt build` on every PR, with a deploy step to prod after merge.
- **Cortex ML couldn't run on my trial account.** I built the feature engineering layer (`user_features`) and wrote the Cortex ML SQL (`snowflake/03_ml_model.sql`), but got an "Insufficient privileges to operate on class CLASSIFICATION" error. This is an account-level restriction — the code itself works, it just needs a Snowflake edition with Cortex ML enabled.

---

## Project structure

```
fakestoreapi-pipeline/
├── scripts/
│   ├── fetch_data.py           # Step 1: Pull from API
│   └── upload_to_s3.py         # Step 2: Push to S3
├── dbt_project/
│   ├── models/
│   │   ├── 01_staging/         # JSON → typed columns
│   │   ├── 02_standardization/ # (reserved)
│   │   ├── 03_business/        # Analytics tables
│   │   └── 04_ml_features/     # Feature engineering
│   ├── tests/                  # Custom data tests
│   ├── dbt_project.yml
│   └── profiles.yml
├── snowflake/
│   ├── 01_setup.sql            # Roles, warehouse, database
│   ├── 02_raw_tables_and_stage.sql
│   └── 03_ml_model.sql         # Cortex ML (proof of concept)
├── airflow/
│   └── dags/
│       └── fakestore_pipeline.py
├── streamlit/
│   └── dashboard.py
├── docker/
│   └── Dockerfile
├── infra/
│   └── architecture.md         # Part 2 deep-dive
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── RUNBOOK.md
```

---

## Current Architecture

```
                    ┌───────────────────────────────────┐
                    │   Airflow (Docker Compose)        │
                    │   scheduled daily, 4 tasks        │
                    └──────┬──────────┬────────────|────┘
                           │          │            |
                           ▼          ▼            ▼
                    ┌──────────┐  ┌───────┐    ┌───────────────┐
                    │  Python  │  │  S3   │    │  Snowflake    │
                    │  scripts │─►│ (raw) │    │  (ext. stage) │
                    │  (fetch) │  │       │───►│  STG → BIZ    │
                    └──────────┘  └───────┘    └───────┬───────┘
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │  Streamlit  │
                                                │  (dashboard)│
                                                └─────────────┘
```

- **Orchestration**: Airflow running locally via Docker Compose (LocalExecutor)
- **Extract**: Python scripts fetch JSON from Fake Store API
- **Store**: Raw JSON lands in S3, Snowflake reads via external stage
- **Transform**: dbt runs 7 models across staging → business layers
- **Serve**: Streamlit dashboard reads from Snowflake BIZ schema

---

## Part 2 — Running this in production

A more detailed write-up is in `infra/architecture.md`, but here's the summary.

### Production Architecture

```
                    ┌───────────────────────────────────┐
                    │    AWS MWAA (Managed Airflow)     │
                    │   scheduled daily, retries on fail│
                    └──────┬──────────┬─────────────|───┘
                           │          │             |
                           ▼          ▼             ▼         
                    ┌──────────┐  ┌───────┐    ┌───────────────┐
                    │  Python  │  │  S3   │    │  Snowflake    │
                    │  scripts │─►│ (raw) │    │incrementalruns│
                    │  (fetch) │  │       │───►│  STG → BIZ→ML │
                    └──────────┘  └───────┘    └───────┬───────┘
                                                       │
                                        ┌──────────────┼──────────────┐
                                        ▼              ▼              ▼
                                 ┌─────────────┐ ┌───────────┐ ┌───────────┐
                                 │  Streamlit  │ │ Elementary│ │   Slack   │
                                 │  (dashboard)│ │ (monitor) │ │  (alerts) │
                                 └─────────────┘ └───────────┘ └───────────┘
```

### How to run daily

The Airflow DAG is already set to `schedule_interval="@daily"`. In production, I'd swap Docker Compose for AWS MWAA (Managed Airflow) so it runs without infra setup. The DAG has 4 tasks that run in sequence: `fetch_data >> upload_to_s3 >> dbt_run >> dbt_test`. If any step fails, Airflow retries once after 5 minutes. If it still fails, the DAG stays in a failed state and waits for someone to look at it.

For a more lightweight option, WE could skip Airflow entirely and run the pipeline from a GitHub Actions workflow on a cron schedule.

### One thing to monitor

**Volumetric anomalies using dbt Elementary.** If the API suddenly returns 0 products or the cart count doubles overnight, something broke upstream. I'd use [Elementary](https://www.elementary-data.com/) — a dbt-native observability package — to catch this. We add `elementary.volume_anomalies` tests in our `schema.yml`, and Elementary tracks row counts over time, flagging runs where the count deviates from the historical pattern. It also supports `freshness_anomalies` and `dimension_anomalies`, and generates an HTML report (`edr report`) with a timeline of all issues. In production, these run as part of `dbt test` in the last Airflow task, with failures can be sent to Slack.

### One improvement before going live

**Incremental loads and date-partitioned S3.** Right now every run does a full refresh. That works for 20 products, but if we had millions of transactions, we'd blow through compute and loading time daily. The fix: partition S3 files by date (`raw/products/dt=2026-03-13/`), use Snowflake's `PATTERN` option in `COPY INTO` to only load today's files, and switch dbt models to `materialized: incremental` with a `loaded_at` timestamp. That alone would cut processing time by 90%+ for large datasets.

### Code quality with SQLFluff

I'd add [SQLFluff](https://sqlfluff.com/) as a SQL linter and formatter to enforce consistent style across all dbt models. In a CI/CD pipeline, `sqlfluff lint` runs on every PR to catch formatting issues and anti-patterns before they reach production. Combined with `sqlfluff fix`, it auto-formats SQL to follow team conventions (indentation, keyword casing, trailing commas, etc.). This keeps the dbt codebase clean and readable as more contributors join.

### Adapting the pipeline for ML

The plan was to use **Snowflake Cortex ML Classification** to predict which product category each user is most interested in. The pieces are all in place:

- **`user_features`** (dbt model) — builds a feature table in the `ML` schema by joining `user_purchase_summary` with `stg_users`. Each row is one user with: total orders, total spend, average order value, items purchased, unique categories bought, favorite category, and city.
- **`snowflake/03_ml_model.sql`** — the SQL to create the classification model via Snowflake's UI (AI & ML → Studio → Classification), train it on `ML.USER_FEATURES` with `FAVORITE_CATEGORY` as the target, then generate predictions using `user_interest_model!PREDICT()` and write them to `ML.USER_INTEREST_PREDICTIONS`.
- **The dashboard** already has an ML tab that reads predictions from Snowflake and shows predicted vs. actual category with confidence scores. If the model doesn't exist, it falls back gracefully.

**Why it didn't work:** My Snowflake trial account didn't have the required privileges to operate on the `SNOWFLAKE.ML.CLASSIFICATION` class — running `SHOW VERSIONS IN CLASS SNOWFLAKE.ML.CLASSIFICATION` returned an "Insufficient privileges" error. This is an account-level restriction that can't be resolved with just role grants; it depends on the Snowflake edition and feature availability. I kept the code as a proof of concept — on an account with Cortex ML enabled, the SQL in `03_ml_model.sql` would work as-is.

**Integrating with the DAG:** Right now the pipeline is `fetch_data >> upload_to_s3 >> dbt_run >> dbt_test`. Since `dbt_run` already builds `ML.USER_FEATURES`, I'd add two tasks after `dbt_test` to automate the prediction step:

```python
# Step 5: Run Cortex ML predictions
ml_predict = BashOperator(
    task_id="ml_predict",
    bash_command=(
        f"cd {PROJECT_DIR} && snowsql -f snowflake/03_ml_model.sql"
        " -o output_format=plain"
    ),
)

# Step 6: Validate predictions table is populated
ml_validate = BashOperator(
    task_id="ml_validate",
    bash_command=(
        f'cd {PROJECT_DIR} && snowsql -q "'
        "SELECT COUNT(*) FROM FAKESTORE_DB.ML.USER_INTEREST_PREDICTIONS"
        " WHERE predictions:class IS NOT NULL\""
    ),
)

fetch_data >> upload_to_s3 >> dbt_run >> dbt_test >> ml_predict >> ml_validate
```

The model itself is created once via the Snowflake UI (or a one-off `CREATE SNOWFLAKE.ML.CLASSIFICATION` call). After that, the DAG only needs to re-run the `PREDICT()` step daily so predictions stay in sync with the latest `user_features` data. If we wanted to retrain periodically, we'd add a weekly DAG (or a branch in this one) that drops and recreates the model.

---

## Tech stack

| Layer | Tool | Why |
|-------|------|-----|
| Extract | Python + requests | Simple REST API, no need for Spark or anything heavy |
| Storage | AWS S3 | Cheap, Snowflake reads from it natively, decouples extract from load |
| Warehouse | Snowflake | Handles JSON, separates compute/storage, free trial available |
| Transform | dbt | SQL-based, testable, version-controlled, clear lineage |
| Orchestration | Airflow (Docker) | Industry standard, shows task dependencies, easy to extend |
| Dashboard | Streamlit | Python-native, fast to build, connects to Snowflake directly |

---

## Links

- **Repo**: https://github.com/suman373-code/Schibsted.git
- **API docs**: https://fakestoreapi.com
- **dbt docs**: Run `dbt docs generate && dbt docs serve` inside `dbt_project/`
- **Airflow UI**: http://localhost:8080 (after `docker-compose up`)
- **Dashboard**: http://localhost:8501 (after `streamlit run streamlit/dashboard.py`)
