"""
Streamlit Dashboard — Fake Store Analytics
-------------------------------------------
A simple report showing key metrics and insights from our Snowflake data pipeline.
Command :  streamlit run streamlit/dashboard.py
"""

import streamlit as st
import snowflake.connector
import pandas as pd
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from streamlit/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# --- Page config ---
st.set_page_config(page_title="Fake Store Analytics", layout="wide")
st.title("🛒 Fake Store Analytics Dashboard for Scheibsted Case Study")
st.markdown("*Real-time metrics from our Snowflake pipeline*")


# --- Connect to Snowflake ---
@st.cache_resource
def get_connection():
    """One connection, reused across the app."""
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database="FAKESTORE_DB",
        schema="BUSINESS",
        warehouse="FAKESTORE_WH",
        role="FAKESTORE_ROLE",
    )


def run_query(sql):
    """Run a query and return a DataFrame. """
    conn = get_connection()
    return pd.read_sql(sql, conn)


# --- Section 1: Big numbers at the top ---
st.header("Overview")

overview = run_query("""
    select
        count(distinct user_id)  as TOTAL_CUSTOMERS,
        count(distinct cart_id)  as TOTAL_ORDERS,
        sum(revenue)             as TOTAL_REVENUE,
        count(*)                 as TOTAL_ITEMS_SOLD
    from order_items
""")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Customers", int(overview["TOTAL_CUSTOMERS"][0]))
col2.metric("Orders", int(overview["TOTAL_ORDERS"][0]))
col3.metric("Revenue", f"${overview['TOTAL_REVENUE'][0]:,.2f}")
col4.metric("Items Sold", int(overview["TOTAL_ITEMS_SOLD"][0]))


# --- Section 2: Revenue by Category ---
st.header("Revenue by Category")

categories = run_query("""
    select
        category,
        total_revenue,
        unique_customers,
        total_items_sold,
        revenue_per_customer
    from revenue_by_category
    order by total_revenue desc
""")

# Bar chart
st.bar_chart(categories.set_index("CATEGORY")["TOTAL_REVENUE"])

# Table with details
st.dataframe(
    categories.rename(columns={
        "CATEGORY": "Category",
        "TOTAL_REVENUE": "Revenue ($)",
        "UNIQUE_CUSTOMERS": "Customers",
        "TOTAL_ITEMS_SOLD": "Items Sold",
        "REVENUE_PER_CUSTOMER": "Rev/Customer ($)",
    }),
    use_container_width=True,
    hide_index=True,
)


# --- Section 3: Top Customers ---
st.header("Top Customers by Spend")

top_customers = run_query("""
    select
        user_id,
        full_name,
        total_orders,
        total_items_purchased,
        total_spend,
        avg_order_value,
        favorite_category
    from user_purchase_summary
    order by total_spend desc
    limit 10
""")

st.dataframe(
    top_customers.rename(columns={
        "USER_ID": "User ID",
        "FULL_NAME": "Name",
        "TOTAL_ORDERS": "Orders",
        "TOTAL_ITEMS_PURCHASED": "Items",
        "TOTAL_SPEND": "Total Spend ($)",
        "AVG_ORDER_VALUE": "Avg Order ($)",
        "FAVORITE_CATEGORY": "Favorite Category",
    }),
    use_container_width=True,
    hide_index=True,
)


# --- Section 4: ML Predictions (if available) ---
st.header("ML: Predicted User Interests")

try:
    predictions = run_query("""
        select
            user_id,
            actual_category,
            predicted_category,
            prediction_confidence,
            total_spend,
            total_orders
        from ML.USER_INTEREST_PREDICTIONS
        order by prediction_confidence desc
    """)

    st.dataframe(
        predictions.rename(columns={
            "USER_ID": "User",
            "ACTUAL_CATEGORY": "Actual Category",
            "PREDICTED_CATEGORY": "Predicted Interest",
            "PREDICTION_CONFIDENCE": "Confidence",
            "TOTAL_SPEND": "Total Spend ($)",
            "TOTAL_ORDERS": "Orders",
        }),
        use_container_width=True,
        hide_index=True,
    )
except Exception:
    st.info(
        "ML predictions not available yet. "
    )


# --- Footer ---
st.markdown("---")
st.caption("Data source: fakestoreapi.com | Pipeline: Python → S3 → Snowflake → dbt → Streamlit")
