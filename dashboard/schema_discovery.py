"""
Run this script once to discover the schema of vw_job_nokey.
Usage: python schema_discovery.py

Output: column names, data types, and sample data.
Use this to fill in the COL_* values in your .env file.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import engine, get_columns, query_df
from config import VIEW_NAME


def main():
    print(f"=== Schema Discovery for [{VIEW_NAME}] ===\n")

    # Test connection
    try:
        from db import test_connection
        test_connection()
        print("Database connection: OK\n")
    except Exception as e:
        print(f"Database connection FAILED: {e}")
        return

    # Get columns
    print(f"--- Columns in {VIEW_NAME} ---")
    try:
        columns = get_columns(VIEW_NAME)
        print(f"{'Column Name':<40s} {'Type':<25s} {'Nullable'}")
        print("-" * 80)
        for col in columns:
            print(f"{col['name']:<40s} {str(col['type']):<25s} {col.get('nullable', '')}")
    except Exception as e:
        print(f"Could not inspect columns: {e}")
        print("Trying SELECT TOP 0 fallback...")

    # Sample data
    print(f"\n--- Sample Data (TOP 5) ---")
    try:
        df = query_df(f"SELECT TOP 5 * FROM {VIEW_NAME}")
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nColumn dtypes:\n{df.dtypes}\n")
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Could not fetch sample data: {e}")

    # Distinct values for likely categorical columns
    print(f"\n--- Distinct value counts (first 50 columns) ---")
    try:
        df_all = query_df(f"SELECT TOP 1000 * FROM {VIEW_NAME}")
        for col in df_all.columns[:50]:
            nunique = df_all[col].nunique()
            if nunique <= 20:
                vals = df_all[col].dropna().unique()
                print(f"\n  {col} ({nunique} unique): {list(vals)}")
    except Exception as e:
        print(f"Could not analyze distinct values: {e}")

    print("\n=== Done. Use the column names above to fill .env COL_* values ===")


if __name__ == '__main__':
    main()
