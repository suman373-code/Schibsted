"""
Step 3: Load data from S3 into Snowflake.

This script connects to Snowflake and runs COPY INTO commands
to pull the JSON files from S3 into our raw tables.
"""

import os

import snowflake.connector

# Snowflake connection details (from environment variables)
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "role": os.getenv("SNOWFLAKE_ROLE", "FAKESTORE_ROLE"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "FAKESTORE_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "FAKESTORE_DB"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA_RAW", "RAW"),
}

# The three tables we want to load
TABLES = ["products", "users", "carts"]


def run_sql(cursor, sql, description=""):
    """Run a SQL statement and print what we're doing."""
    if description:
        print(f"  {description}")
    cursor.execute(sql)
    print(f"    → Done. ({cursor.rowcount} rows)")


def load_data():
    """
    For each endpoint, truncate the raw table and COPY fresh data from S3.
    This gives us a clean, idempotent reload every run.
    """
    print("Connecting to Snowflake...")
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cursor = conn.cursor()

    try:
        for table in TABLES:
            print(f"\nLoading {table}...")

            # Clear old data (full refresh approach — simple and predictable)
            run_sql(
                cursor,
                f"TRUNCATE TABLE IF EXISTS RAW_{table.upper()};",
                f"Clearing RAW_{table.upper()}",
            )

            # Copy new data from S3 stage
            run_sql(
                cursor,
                f"""
                COPY INTO RAW_{table.upper()} (raw_data, source_file)
                FROM (
                    SELECT $1::VARIANT, METADATA$FILENAME
                    FROM @S3_RAW_STAGE/{table}/
                )
                FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE)
                ON_ERROR = 'CONTINUE';
                """,
                f"Copying from S3 → RAW_{table.upper()}",
            )

        print("\nAll tables loaded successfully!")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    load_data()
