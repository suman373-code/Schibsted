-- ============================================================================
-- Step 3: ML Classification Model (Snowflake Cortex ML)
-- ============================================================================
-- Predicts which product category each user is most interested in
-- Uses dbt-created ML.USER_FEATURES as training data
--
-- NOTE: The Classification model is created via the Snowflake UI:
--   AI & ML → Studio → Classification → + Create
--   Table:  FAKESTORE_DB.ML.USER_FEATURES
--   Target: FAVORITE_CATEGORY
--   Name:   user_interest_model
-- ============================================================================

-----------------------------------------------------------
-- SETUP
-----------------------------------------------------------
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE FAKESTORE_WH;
USE DATABASE FAKESTORE_DB;
USE SCHEMA ML;

-- Inspect training data (ML.USER_FEATURES created by dbt run)
SELECT * FROM USER_FEATURES LIMIT 10;

-----------------------------------------------------------
-- VERIFY MODEL (run after UI creation completes)
-----------------------------------------------------------
CALL user_interest_model!SHOW_TRAINING_LOGS();

-----------------------------------------------------------
-- GENERATE PREDICTIONS
-----------------------------------------------------------

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

-----------------------------------------------------------
-- INSPECT RESULTS
-----------------------------------------------------------

-- Model evaluation metrics
CALL user_interest_model!SHOW_EVALUATION_METRICS();
CALL user_interest_model!SHOW_GLOBAL_EVALUATION_METRICS();
CALL user_interest_model!SHOW_CONFUSION_MATRIX();

-- Feature importance
CALL user_interest_model!SHOW_FEATURE_IMPORTANCE();
