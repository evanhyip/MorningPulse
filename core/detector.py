import json
import os
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import requests

load_dotenv()

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_TOKEN = os.getenv("SNOWFLAKE_TOKEN")


def fetch_telemetry_from_snowflake() -> pd.DataFrame:
    """Fetches telemetry metrics directly from Snowflake via the Statements REST API."""
    if not SNOWFLAKE_ACCOUNT or not SNOWFLAKE_TOKEN:
        raise ValueError(
            "Missing SNOWFLAKE_ACCOUNT or SNOWFLAKE_TOKEN in environment variables."
        )

    url = (
        f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    )
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Use TO_VARCHAR so Snowflake returns clean '2026-10-23' strings instead of epoch days
    payload = {
        "statement": """
            SELECT 
                TO_VARCHAR(METRIC_DATE, 'YYYY-MM-DD') AS METRIC_DATE, 
                DEPARTMENT, 
                METRIC_NAME, 
                METRIC_VALUE, 
                UNIT 
            FROM MORNINGPULSE_DB.TELEMETRY.BUSINESS_METRICS 
            ORDER BY METRIC_NAME, METRIC_DATE ASC;
        """,
        "warehouse": "COMPUTE_WH",
        "database": "MORNINGPULSE_DB",
        "schema": "TELEMETRY",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    cols = [
        col["name"].lower() for col in result["resultSetMetaData"]["rowType"]
    ]
    rows = result.get("data", [])

    df = pd.DataFrame(rows, columns=cols)

    # Now standard ISO parsing succeeds without ambiguity
    df["metric_date"] = pd.to_datetime(df["metric_date"], format="%Y-%m-%d")
    df["metric_value"] = pd.to_numeric(df["metric_value"])

    return df


def detect_today_anomalies(
    df: pd.DataFrame = None, z_threshold: float = 2.5
) -> list[dict]:
    """Calculates 14-day rolling baseline and identifies statistical outliers."""
    if df is None:
        df = fetch_telemetry_from_snowflake()

    if df.empty:
        return []

    df_sorted = df.sort_values(by=["metric_name", "metric_date"]).copy()

    # 14-day rolling baseline calculation (excluding current day via shift)
    df_sorted["rolling_avg"] = df_sorted.groupby("metric_name")[
        "metric_value"
    ].transform(lambda s: s.shift(1).rolling(14, min_periods=7).mean())

    df_sorted["rolling_std"] = df_sorted.groupby("metric_name")[
        "metric_value"
    ].transform(lambda s: s.shift(1).rolling(14, min_periods=7).std())

    # Replace zero std with NaN to prevent divide-by-zero
    rolling_std_safe = df_sorted["rolling_std"].replace(0, np.nan)
    df_sorted["z_score"] = (
        df_sorted["metric_value"] - df_sorted["rolling_avg"]
    ) / rolling_std_safe

    # Select the most recent record per metric rather than a single global date
    latest_records = df_sorted.groupby("metric_name").tail(1)
    outliers = latest_records[latest_records["z_score"].abs() >= z_threshold]

    anomalies = []
    for _, row in outliers.iterrows():
        base = row["rolling_avg"]
        curr = row["metric_value"]

        # Safe percentage delta calculation
        if pd.isna(base) or base == 0:
            pct_delta_str = "N/A (Zero Baseline)"
        else:
            pct_change = ((curr - base) / base) * 100
            pct_delta_str = f"{pct_change:+.1f}%"

        anomalies.append(
            {
                "department": row["department"],
                "metric_name": row["metric_name"],
                "current_value": round(float(curr), 2),
                "expected_baseline": (
                    round(float(base), 2) if pd.notna(base) else None
                ),
                "percent_delta": pct_delta_str,
                "z_score": round(float(row["z_score"]), 2),
                "unit": row["unit"],
            }
        )

    return anomalies


if __name__ == "__main__":
    results = detect_today_anomalies()
    print(f"Detected {len(results)} anomalies for the morning brief:\n")
    print(json.dumps(results, indent=2))