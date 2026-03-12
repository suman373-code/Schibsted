"""
Airflow DAG — Fake Store Pipeline
-----------------------------------
Runs the full pipeline daily:
  1. Fetch data from API
  2. Upload to S3
  3. Load into Snowflake
  4. Run dbt models
  5. (Optional) Refresh ML model

Nothing fancy — just calls our Python scripts in order.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Where our project lives inside the Docker container
PROJECT_DIR = "/opt/airflow/project"

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fakestore_pipeline",
    description="Fetch → S3 → Snowflake → dbt → ML",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["fakestore", "pipeline"],
) as dag:

    # Step 1: Fetch data from the API
    fetch_data = BashOperator(
        task_id="fetch_data",
        bash_command=f"python {PROJECT_DIR}/scripts/fetch_data.py",
    )

    # Step 2: Upload raw JSON files to S3
    upload_to_s3 = BashOperator(
        task_id="upload_to_s3",
        bash_command=f"python {PROJECT_DIR}/scripts/upload_to_s3.py",
    )

    # Step 3: Load from S3 into Snowflake raw tables
    load_to_snowflake = BashOperator(
        task_id="load_to_snowflake",
        bash_command=f"python {PROJECT_DIR}/scripts/load_to_snowflake.py",
    )

    # Step 4: Run dbt to build staging + business models
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt_project && dbt run --profiles-dir .",
    )

    # Step 5: Run dbt tests
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt_project && dbt test --profiles-dir .",
    )

    # The order matters
    fetch_data >> upload_to_s3 >> load_to_snowflake >> dbt_run >> dbt_test
