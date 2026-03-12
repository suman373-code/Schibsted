-- ============================================================================
-- Raw Tables + S3 External Stage
-- ============================================================================

-- Stage creation needs ACCOUNTADMIN for storage integration
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE FAKESTORE_WH;
USE DATABASE FAKESTORE_DB;
USE SCHEMA RAW;

-- External stage pointing to S3 bucket
CREATE OR REPLACE STAGE S3_RAW_STAGE
    URL = 's3://schibsted-case-raw-data/raw/'
    CREDENTIALS = (
        AWS_KEY_ID = 'your_aws_key_here'
        AWS_SECRET_KEY = 'your_aws_secret_here'
    )
    FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE);

-- Grant stage usage to our pipeline role
GRANT USAGE ON STAGE FAKESTORE_DB.RAW.S3_RAW_STAGE TO ROLE FAKESTORE_ROLE;

-- Verify the stage can see files (will be empty until you run upload_to_s3.py):
-- LIST @S3_RAW_STAGE;

-- Switch to pipeline role for table creation
USE ROLE FAKESTORE_ROLE;

-- Raw tables: one per endpoint
CREATE TABLE IF NOT EXISTS RAW_PRODUCTS (
    raw_data    VARIANT,
    source_file VARCHAR,
    loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS RAW_USERS (
    raw_data    VARIANT,
    source_file VARCHAR,
    loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS RAW_CARTS (
    raw_data    VARIANT,
    source_file VARCHAR,
    loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
