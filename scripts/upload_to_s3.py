"""
This script Uploads raw JSON files to AWS S3.

"""

import os
import glob

import boto3
from dotenv import load_dotenv

# Load .env file so AWS credentials are available
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Read from environment variables (set in .env or Airflow connections)
BUCKET_NAME = os.getenv("S3_BUCKET", "schibsted-case-raw-data")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Local folder where fetch_data.py saves files
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def get_s3_client():
    """Create an S3 client. Uses default AWS credential chain (env vars, ~/.aws, IAM role)."""
    return boto3.client("s3", region_name=AWS_REGION)


def create_bucket_if_needed(s3):
    """Make sure our bucket exists. Create it if not."""
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' exists.")
    except Exception:
        print(f"Creating bucket '{BUCKET_NAME}'...")
        create_args = {"Bucket": BUCKET_NAME}
        if AWS_REGION != "us-east-1":
            create_args["CreateBucketConfiguration"] = {"LocationConstraint": AWS_REGION}
        s3.create_bucket(**create_args)
        print(f"  Created.")


def upload_files():
    """
    Upload all JSON files from data/raw/ to S3.
    Files go to: s3://bucket/raw/products/products_20260308_120000.json
    """
    s3 = get_s3_client()
    create_bucket_if_needed(s3)

    json_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.json"))
    if not json_files:
        print("No JSON files found. Run fetch_data.py first.")
        return {}

    uploaded = {}

    for filepath in json_files:
        filename = os.path.basename(filepath)

        # Figure out which endpoint this file is for (products, users, or carts)
        # Filename looks like: products_20260308_120000.json
        endpoint = filename.split("_")[0]

        s3_key = f"raw/{endpoint}/{filename}"

        print(f"Uploading {filename} → s3://{BUCKET_NAME}/{s3_key}")
        s3.upload_file(filepath, BUCKET_NAME, s3_key)

        uploaded[endpoint] = f"s3://{BUCKET_NAME}/{s3_key}"

    return uploaded


if __name__ == "__main__":
    result = upload_files()
    print("\nDone! Uploaded files:")
    for name, uri in result.items():
        print(f"  {name}: {uri}")
