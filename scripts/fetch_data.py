"""
Step 1: Fetch data from the Fake Store API.

This script fetches data from https://fakestoreapi.com
and saves each as a JSON file locally.
"""

import json
import os
from datetime import datetime, timezone

import requests

# Where to save the raw JSON files
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# The three endpoints we care about
ENDPOINTS = {
    "products": "https://fakestoreapi.com/products",
    "users": "https://fakestoreapi.com/users",
    "carts": "https://fakestoreapi.com/carts",
}


def fetch_and_save():
    """Fetch each endpoint and save it as a timestamped JSON file."""

    # Create the output folder if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Timestamp for this run — so we can track when data was pulled
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    saved_files = {}

    for name, url in ENDPOINTS.items():
        print(f"Fetching {name} from {url}...")

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        print(f"  Got {len(data)} records.")

        # Save to file like: products_20260308_120000.json
        filename = f"{name}_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"  Saved to {filepath}")
        saved_files[name] = filepath

    return saved_files


if __name__ == "__main__":
    files = fetch_and_save()
    print("\nDone! Files saved:")
    for name, path in files.items():
        with open(path, "r") as f:
            record_count = len(json.load(f))
        print(f"  {name}: {path} ({record_count} records)")
