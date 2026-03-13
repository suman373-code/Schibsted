
-- Step 3: ML Classification Model (Snowflake Cortex ML)
-- Predicts which product category each user is most interested in
-- Uses dbt-created ML.USER_FEATURES as training data

-- SETUP

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE FAKESTORE_WH;
USE DATABASE FAKESTORE_DB;
USE SCHEMA ML;

-- Check training data (ML.USER_FEATURES created by dbt run)
SELECT * FROM USER_FEATURES LIMIT 10;


-- CREATE MODEL 
CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION user_interest_model(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'USER_FEATURES'),
    TARGET_COLNAME => 'FAVORITE_CATEGORY'
);


-- VERIFY MODEL CREATION

CALL user_interest_model!SHOW_TRAINING_LOGS();


-- GENERATE PREDICTIONS

-- Generate predictions for all users
CREATE OR REPLACE TABLE ML.USER_INTEREST_PREDICTIONS AS
SELECT
    *,
    user_interest_model!PREDICT(
        OBJECT_CONSTRUCT(*),
        {'ON_ERROR': 'SKIP'}
    ) AS predictions
FROM USER_FEATURES;

-- View raw predictions
SELECT * FROM ML.USER_INTEREST_PREDICTIONS;

-- Parse predictions into readable columns
SELECT
    USER_ID,
    FAVORITE_CATEGORY AS ACTUAL_CATEGORY,
    predictions:class::STRING AS PREDICTED_CATEGORY,
    ROUND(predictions['probability'][predictions:class::STRING], 3) AS PREDICTION_CONFIDENCE,
    TOTAL_SPEND,
    TOTAL_ORDERS
FROM ML.USER_INTEREST_PREDICTIONS;


-- INSPECT RESULTS


-- Model evaluation metrics
CALL user_interest_model!SHOW_EVALUATION_METRICS();
CALL user_interest_model!SHOW_GLOBAL_EVALUATION_METRICS();
CALL user_interest_model!SHOW_CONFUSION_MATRIX();

-- Feature importance
CALL user_interest_model!SHOW_FEATURE_IMPORTANCE();
