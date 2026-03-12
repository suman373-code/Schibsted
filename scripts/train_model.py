"""
train_model.py — Real ML with scikit-learn
-------------------------------------------
Reads user features from Snowflake, trains a Random Forest classifier
to predict which product category a user prefers, then writes
predictions back to Snowflake.

Why Random Forest?
- Works well with small datasets (we only have 5 users)
- Handles both numeric and categorical features
- Gives us prediction probabilities (confidence scores)
- No feature scaling needed

Run:  python scripts/train_model.py
"""

import os
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import LeaveOneOut, cross_val_predict

load_dotenv()


# ------------------------------------------------------------------
# Step 1: Connect to Snowflake and read the feature table
# ------------------------------------------------------------------
def get_connection():
    """Connect to Snowflake using .env credentials."""
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database="FAKESTORE_DB",
        warehouse="FAKESTORE_WH",
        role="FAKESTORE_ROLE",
    )


print("Step 1: Reading features from Snowflake...")
conn = get_connection()
df = pd.read_sql("SELECT * FROM ML.USER_FEATURES", conn)
print(f"  Loaded {len(df)} users with {len(df.columns)} features")
print(f"  Columns: {list(df.columns)}")


# ------------------------------------------------------------------
# Step 2: Prepare features for the model
# ------------------------------------------------------------------
print("\nStep 2: Preparing features...")

# The target we want to predict
target_col = "FAVORITE_CATEGORY"

# Numeric features the model will learn from
numeric_features = [
    "TOTAL_ORDERS",
    "TOTAL_ITEMS_PURCHASED",
    "TOTAL_SPEND",
    "AVG_ITEM_SPEND",
    "AVG_ORDER_VALUE",
    "UNIQUE_CATEGORIES_BOUGHT",
]

# Encode the city column as a number (ML models need numbers, not text)
city_encoder = LabelEncoder()
df["CITY_ENCODED"] = city_encoder.fit_transform(df["CITY"])

# Build the feature matrix (X) and target vector (y)
feature_cols = numeric_features + ["CITY_ENCODED"]
X = df[feature_cols]
y = df[target_col]

print(f"  Features: {feature_cols}")
print(f"  Target: {target_col}")
print(f"  Categories to predict: {list(y.unique())}")


# ------------------------------------------------------------------
# Step 3: Train the model with Leave-One-Out cross-validation
# ------------------------------------------------------------------
print("\nStep 3: Training Random Forest with Leave-One-Out CV...")

# With only 5 users, we use Leave-One-Out:
# Train on 4 users, predict the 5th. Repeat for each user.
# This way every user gets a "fair" prediction.
model = RandomForestClassifier(
    n_estimators=100,      # 100 decision trees vote together
    random_state=42,       # same results every run
    max_depth=3,           # keep trees simple (small dataset)
)

loo = LeaveOneOut()

# cross_val_predict: for each user, train on the others and predict this one
predictions = cross_val_predict(model, X, y, cv=loo)

# Now train the final model on ALL data (for feature importance + probabilities)
model.fit(X, y)
probabilities = model.predict_proba(X)

# Get the confidence for each prediction (max probability)
confidence = [round(max(prob), 4) for prob in probabilities]

print(f"  Model trained with {model.n_estimators} trees")
print(f"  Feature importance:")
for feat, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
    print(f"    {feat}: {imp:.3f}")


# ------------------------------------------------------------------
# Step 4: Build the results DataFrame
# ------------------------------------------------------------------
print("\nStep 4: Building predictions table...")

results = pd.DataFrame({
    "USER_ID": df["USER_ID"],
    "TOTAL_SPEND": df["TOTAL_SPEND"],
    "TOTAL_ORDERS": df["TOTAL_ORDERS"],
    "ACTUAL_CATEGORY": df[target_col],
    "PREDICTED_CATEGORY": predictions,           # from Leave-One-Out
    "PREDICTION_CONFIDENCE": confidence,          # from full model
})

# How accurate were the LOO predictions?
correct = (results["ACTUAL_CATEGORY"] == results["PREDICTED_CATEGORY"]).sum()
total = len(results)
print(f"  Accuracy: {correct}/{total} ({correct/total*100:.0f}%)")
print(f"\n  Predictions:")
for _, row in results.iterrows():
    match = "✓" if row["ACTUAL_CATEGORY"] == row["PREDICTED_CATEGORY"] else "✗"
    print(f"    User {int(row['USER_ID'])}: actual={row['ACTUAL_CATEGORY']}, "
          f"predicted={row['PREDICTED_CATEGORY']}, "
          f"confidence={row['PREDICTION_CONFIDENCE']:.2f} {match}")


# ------------------------------------------------------------------
# Step 5: Write predictions back to Snowflake
# ------------------------------------------------------------------
print("\nStep 5: Writing predictions to Snowflake (ML.USER_INTEREST_PREDICTIONS)...")

cursor = conn.cursor()

# Drop and recreate the table
cursor.execute("CREATE OR REPLACE TABLE ML.USER_INTEREST_PREDICTIONS ("
               "USER_ID INTEGER, "
               "TOTAL_SPEND FLOAT, "
               "TOTAL_ORDERS INTEGER, "
               "ACTUAL_CATEGORY STRING, "
               "PREDICTED_CATEGORY STRING, "
               "PREDICTION_CONFIDENCE FLOAT)")

# Insert each row
for _, row in results.iterrows():
    cursor.execute(
        "INSERT INTO ML.USER_INTEREST_PREDICTIONS VALUES (%s, %s, %s, %s, %s, %s)",
        (int(row["USER_ID"]), float(row["TOTAL_SPEND"]), int(row["TOTAL_ORDERS"]),
         row["ACTUAL_CATEGORY"], row["PREDICTED_CATEGORY"], float(row["PREDICTION_CONFIDENCE"]))
    )

print(f"  Written {len(results)} predictions to Snowflake")

cursor.close()
conn.close()
print("\nDone! Check your Streamlit dashboard — ML section should now show data.")
