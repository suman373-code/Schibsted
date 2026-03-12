# Runbook — Fake Store Data Pipeline

This covers how to run the pipeline both ways: manually from your terminal, or automated through Airflow. Pick whichever fits your situation — manual is great for debugging, Airflow is what you'd use day-to-day.

---

## Prerequisites

Before either method, make sure you have:

- **Python 3.11+** installed
- **Docker Desktop** running (only needed for Airflow)
- A `.env` file in the project root with your credentials filled in (copy from `.env.example`)
- Snowflake objects created — run `snowflake/01_setup.sql` and `snowflake/02_raw_tables_and_stage.sql` in a Snowflake worksheet first

---

## Option A: Run manually

This is useful when you're developing, debugging, or just want to run one step at a time.

### 1. Activate the virtual environment

```bash
cd C:\personal\Schibsted\fakestoreapi-pipeline

python -m venv .venv            # only the first time
source .venv/Scripts/activate   # Windows (Git Bash)
# or: .venv\Scripts\activate    # Windows (CMD / PowerShell)

pip install -r requirements.txt # only the first time
```

### 2. Fetch data from the API

```bash
python scripts/fetch_data.py
```

This calls fakestoreapi.com and saves JSON files locally under `data/`. You should see output like:

```
Fetching products... done (20 items)
Fetching users... done (10 items)
Fetching carts... done (7 items)
```

### 3. Upload to S3

```bash
python scripts/upload_to_s3.py
```

Pushes the local JSON files to your S3 bucket, organized by endpoint (`products/`, `users/`, `carts/`). Make sure your AWS credentials in `.env` are correct.

### 4. Load into Snowflake

```bash
python scripts/load_to_snowflake.py
```

Runs `COPY INTO` from the S3 external stage into the raw VARIANT tables in Snowflake. This does a full refresh (truncate + load).

### 5. Run dbt models

```bash
cd dbt_project
dbt run --profiles-dir .
```

Builds all 7 models in order:
- **01_staging**: `stg_products`, `stg_users`, `stg_carts` (views that parse raw JSON)
- **02_standardization**: reserved for future use
- **03_business**: `order_items`, `user_purchase_summary`, `revenue_by_category` (tables)
- **04_ml_features**: `user_features` (input table for ML model)

### 6. Run dbt tests

```bash
dbt test --profiles-dir .
```

Runs 22 tests — schema tests (unique, not_null) and unit tests (mock data validation). All should pass. If any fail, the output tells you exactly which test and why.

### 7. (Optional) Check the dashboard

```bash
cd ..
streamlit run streamlit/dashboard.py
```

Opens at http://localhost:8501. Shows revenue by category, top customers, and ML predictions (if available).

### 8. (Optional) ML model

After dbt finishes, the `ML.USER_FEATURES` table is ready. Create the classification model through Snowflake UI (AI & ML → Studio → Classification), then run the prediction queries from `snowflake/03_ml_model.sql`.

---

## Option B: Run with Airflow

This is the automated approach. Airflow runs all 5 steps in sequence, retries on failure, and keeps logs for every run.

### 1. Make sure Docker Desktop is running

Check that Docker is up:

```bash
docker info
```

If you get an error, open Docker Desktop and wait for it to start.

### 2. Start the Airflow stack

```bash
cd C:\personal\Schibsted\fakestoreapi-pipeline
docker compose up -d --build
```

This spins up 3 containers:
- **postgres** — Airflow's metadata database
- **airflow-webserver** — the UI at http://localhost:8080
- **airflow-scheduler** — picks up and runs DAGs on schedule

First run takes a minute or two (builds the image, runs DB migrations, creates the admin user).

### 3. Open the Airflow UI

Go to **http://localhost:8080** and log in:
- Username: `airflow`
- Password: `airflow`

### 4. Trigger the pipeline

Find `fakestore_pipeline` in the DAG list. It runs automatically at midnight UTC every day, but you can trigger it manually:

1. Click the play button (▶) on the right side
2. Click "Trigger DAG"

### 5. Monitor the run

Click into the DAG to see the task graph. The 5 tasks run in this order:

```
fetch_data → upload_to_s3 → load_to_snowflake → dbt_run → dbt_test
```

- **Green** = success
- **Red** = failed (click the task → Logs to see what went wrong)
- **Yellow** = running
- **Light green** = queued

A full run typically takes about 60 seconds.

### 6. Check logs for a specific task

Click any task box → **Log** tab. This shows the full stdout/stderr from the BashOperator, including dbt output and any Python errors.

### 7. Stop Airflow

```bash
docker compose down
```

Add `-v` to also wipe the Postgres data (metadata, run history):

```bash
docker compose down -v
```

---

## Troubleshooting

### "Module not found" errors in Airflow

The Docker image installs packages from `requirements.txt`. If you added a new dependency, rebuild:

```bash
docker compose down
docker compose up -d --build
```

### dbt test failures

Run dbt tests manually to see detailed output:

```bash
cd dbt_project && dbt test --profiles-dir .
```

Common causes: Snowflake session timed out, data hasn't loaded yet, or the API returned unexpected data.

### Snowflake connection errors

Double-check your `.env` file. The account format should be `your_org-your_account` (not a URL). Make sure the password doesn't have special characters that need escaping.

### S3 upload failures

Verify your AWS credentials and that the bucket exists in the right region. The bucket name in `.env` should be just the name, not `s3://bucket-name`.

### Airflow containers won't start

```bash
docker compose logs airflow-webserver
docker compose logs airflow-scheduler
```

Usually it's a port conflict (something else on 8080) or Docker not having enough memory allocated.

### Dashboard shows "no data"

The pipeline hasn't run yet, or dbt models haven't been built. Run the pipeline first (either method), then refresh the dashboard.

---

## Daily operations

| Task | How |
|------|-----|
| Run the pipeline | Airflow does it automatically at midnight UTC. Or trigger manually from the UI. |
| Re-run a failed task | In Airflow UI, click the failed task → "Clear" to retry it |
| Run just dbt | `cd dbt_project && dbt run --profiles-dir .` |
| Run just tests | `cd dbt_project && dbt test --profiles-dir .` |
| Check Airflow logs | http://localhost:8080 → click DAG → click task → Log tab |
| Rebuild Airflow image | `docker compose down && docker compose up -d --build` |
| Stop everything | `docker compose down` |
| Full reset | `docker compose down -v` (deletes Airflow metadata too) |
