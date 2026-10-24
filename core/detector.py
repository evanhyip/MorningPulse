import os
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_TOKEN = os.getenv("SNOWFLAKE_TOKEN")

# Metrics where an increase represents positive business performance
HIGHER_IS_BETTER = {
    "daily_net_revenue_usd",
    "average_order_value_usd",
    "new_user_signups",
    "daily_active_users",
    "csat_customer_satisfaction_pct",
}


def fetch_telemetry_from_snowflake() -> pd.DataFrame:
    """Fetches metric telemetry records from Snowflake via the Statements REST API."""
    url = f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Explicitly format METRIC_DATE to ISO string to avoid epoch day integers
    sql = """
        SELECT 
            TO_VARCHAR(METRIC_DATE, 'YYYY-MM-DD') AS METRIC_DATE,
            DEPARTMENT,
            METRIC_NAME,
            METRIC_VALUE,
            UNIT
        FROM MORNINGPULSE_DB.TELEMETRY.BUSINESS_METRICS
        ORDER BY METRIC_NAME, METRIC_DATE ASC;
    """
    payload = {"statement": sql, "warehouse": "COMPUTE_WH"}

    res = requests.post(url, headers=headers, json=payload, timeout=45)
    res.raise_for_status()

    data = res.json().get("data", [])
    df = pd.DataFrame(
        data,
        columns=[
            "metric_date",
            "department",
            "metric_name",
            "metric_value",
            "unit",
        ],
    )
    df["metric_value"] = pd.to_numeric(df["metric_value"])

    # Handle both formatted date strings and epoch-day integers
    try:
        numeric_days = pd.to_numeric(df["metric_date"])
        df["metric_date"] = pd.to_datetime(numeric_days, unit="D", origin="unix")
    except (ValueError, TypeError):
        df["metric_date"] = pd.to_datetime(df["metric_date"], format="%Y-%m-%d")

    return df


def detect_today_anomalies(
    df: pd.DataFrame | str | None = None, z_threshold: float = 2.5
) -> dict[str, list[dict]]:
    """Calculates a 14-day rolling window baseline and categorizes outliers

    into operational risks and positive growth opportunities.
    """
    if isinstance(df, str):
        df = pd.read_csv(df)
        df["metric_date"] = pd.to_datetime(df["metric_date"])
    elif df is None:
        df = fetch_telemetry_from_snowflake()

    if df.empty:
        return {"risks": [], "opportunities": []}

    df_sorted = df.sort_values(by=["metric_name", "metric_date"]).copy()

    # Calculate 14-day rolling baseline shifted by 1 to exclude the evaluated day
    df_sorted["rolling_avg"] = df_sorted.groupby("metric_name")[
        "metric_value"
    ].transform(lambda s: s.shift(1).rolling(14, min_periods=7).mean())
    df_sorted["rolling_std"] = df_sorted.groupby("metric_name")[
        "metric_value"
    ].transform(lambda s: s.shift(1).rolling(14, min_periods=7).std())

    # Protect against division by zero
    rolling_std_safe = df_sorted["rolling_std"].replace(0, np.nan)
    df_sorted["z_score"] = (
        df_sorted["metric_value"] - df_sorted["rolling_avg"]
    ) / rolling_std_safe

    # Isolate the latest date's records across all metrics
    latest_records = df_sorted.groupby("metric_name").tail(1)
    outliers = latest_records[latest_records["z_score"].abs() >= z_threshold]

    risks: list[dict] = []
    opportunities: list[dict] = []

    for _, row in outliers.iterrows():
        base = row["rolling_avg"]
        curr = row["metric_value"]
        z = row["z_score"]
        m_name = row["metric_name"]

        pct_change = (
            ((curr - base) / base) * 100 if base and not pd.isna(base) else 0.0
        )
        is_higher_better = m_name in HIGHER_IS_BETTER

        # Determine directional impact
        # Risk: higher-is-better dropped, or lower-is-better spiked
        is_risk = (is_higher_better and z < 0) or (
            not is_higher_better and z > 0
        )

        item = {
            "department": row["department"],
            "metric_name": m_name,
            "current_value": round(float(curr), 2),
            "expected_baseline": (
                round(float(base), 2) if pd.notna(base) else None
            ),
            "percent_delta": f"{pct_change:+.1f}%",
            "z_score": round(float(z), 2),
            "unit": row["unit"],
            "type": "risk" if is_risk else "opportunity",
        }

        if is_risk:
            risks.append(item)
        else:
            opportunities.append(item)

    return {"risks": risks, "opportunities": opportunities}


if __name__ == "__main__":
    results = detect_today_anomalies("data/seed_metrics.csv")
    print(
        f"Detected {len(results['risks'])} Risks and {len(results['opportunities'])} Opportunities:"
    )
    print("RISKS:", results["risks"])
    print("OPPORTUNITIES:", results["opportunities"])