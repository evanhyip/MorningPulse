"""
core/detector.py
Dynamic Telemetry Ingestion & Statistical Anomaly Detection for MorningPulse.
Handles Snowflake epoch date representation ('20690'), schema aliases, and Z-scores.
"""

import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import requests

load_dotenv()


def get_env_or_secret(key: str, default: str = "") -> str:
    """Checks os.environ first, then Streamlit secrets if running inside Streamlit."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def get_snowflake_config(
    database: Optional[str] = None,
    schema: Optional[str] = None,
    table: Optional[str] = None,
    warehouse: Optional[str] = None,
) -> Dict[str, str]:
    return {
        "account": get_env_or_secret("SNOWFLAKE_ACCOUNT"),
        "token": get_env_or_secret("SNOWFLAKE_TOKEN"),
        "warehouse": warehouse or get_env_or_secret("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "database": database or get_env_or_secret("SNOWFLAKE_DATABASE", "MORNINGPULSE_DB"),
        "schema": schema or get_env_or_secret("SNOWFLAKE_SCHEMA", "TELEMETRY"),
        "table": table or get_env_or_secret("SNOWFLAKE_TABLE", "BUSINESS_METRICS"),
    }


def parse_snowflake_date(series: pd.Series) -> pd.Series:
    """
    Parses dates returned by Snowflake SQL API v2.
    Snowflake returns DATE columns as string integers representing days since 1970-01-01 (e.g. '20690').
    """
    # Clean string inputs
    str_series = series.astype(str).str.strip()

    # Try numeric epoch conversion first
    numeric_days = pd.to_numeric(str_series, errors="coerce")
    if numeric_days.notna().sum() > 0:
        # Scale check: days since epoch (e.g. 15000 to 40000 covers 2011 to 2079)
        sample = numeric_days.dropna().iloc[0]
        if sample < 100000:
            return pd.to_datetime(numeric_days, unit="D", origin="1970-01-01")
        elif sample < 10000000000:
            return pd.to_datetime(numeric_days, unit="s", origin="1970-01-01")
        else:
            return pd.to_datetime(numeric_days, unit="ms", origin="1970-01-01")

    # Fallback to standard ISO / string date parsing
    return pd.to_datetime(str_series, errors="coerce")


def normalize_telemetry_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizes arbitrary table schema into MorningPulse contract."""
    if df.empty:
        return pd.DataFrame(
            columns=["metric_date", "metric_name", "metric_value", "department", "unit"]
        )

    df = df.copy()

    # Clean headers to lowercase
    df.columns = [re.sub(r"[\s\-]+", "_", str(col).strip().lower()) for col in df.columns]

    # Map candidate column names
    date_candidates = ["metric_date", "date", "timestamp", "created_at", "day", "dt"]
    name_candidates = ["metric_name", "kpi", "metric", "name", "measure"]
    val_candidates = ["metric_value", "value", "val", "amount", "score"]
    dept_candidates = ["department", "dept", "team", "category", "service"]
    unit_candidates = ["unit", "units", "uom"]

    rename_map = {}
    for col in df.columns:
        if col in date_candidates and "metric_date" not in rename_map.values():
            rename_map[col] = "metric_date"
        elif col in name_candidates and "metric_name" not in rename_map.values():
            rename_map[col] = "metric_name"
        elif col in val_candidates and "metric_value" not in rename_map.values():
            rename_map[col] = "metric_value"
        elif col in dept_candidates and "department" not in rename_map.values():
            rename_map[col] = "department"
        elif col in unit_candidates and "unit" not in rename_map.values():
            rename_map[col] = "unit"

    df = df.rename(columns=rename_map)

    # Validate core requirements
    for req in ["metric_date", "metric_name", "metric_value"]:
        if req not in df.columns:
            raise ValueError(f"Missing required column '{req}'. Found: {list(df.columns)}")

    if "department" not in df.columns:
        df["department"] = "Core Operations"

    if "unit" not in df.columns:
        df["unit"] = ""

    # Parse and clean values
    val_str = df["metric_value"].astype(str).str.replace(r"[$,% ]", "", regex=True)
    df["metric_value"] = pd.to_numeric(val_str, errors="coerce")

    # Parse date using Snowflake epoch parser
    df["metric_date"] = parse_snowflake_date(df["metric_date"])

    # Drop missing rows
    df = df.dropna(subset=["metric_date", "metric_value"])

    return df[["metric_date", "metric_name", "metric_value", "department", "unit"]]


def fetch_telemetry_from_snowflake(
    database: Optional[str] = None,
    schema: Optional[str] = None,
    table: Optional[str] = None,
    warehouse: Optional[str] = None,
    lookback_days: int = 14,
) -> pd.DataFrame:
    """Fetches and normalizes telemetry data from Snowflake."""
    cfg = get_snowflake_config(database=database, schema=schema, table=table, warehouse=warehouse)

    if not cfg["account"] or not cfg["token"]:
        raise ValueError("Missing SNOWFLAKE_ACCOUNT or SNOWFLAKE_TOKEN.")

    db = cfg["database"].strip(' "\'')
    sch = cfg["schema"].strip(' "\'')
    tbl = cfg["table"].strip(' "\'')
    wh = cfg["warehouse"].strip(' "\'')

    # Double-quote exact table identifier
    full_table = f'"{db}"."{sch}"."{tbl}"'
    url = f'https://{cfg["account"]}.snowflakecomputing.com/api/v2/statements'
    headers = {
        "Authorization": f'Bearer {cfg["token"]}',
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    sql = f"SELECT * FROM {full_table};"
    payload = {"statement": sql, "warehouse": wh}

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        error_msg = response.json().get("message", response.text)
        raise RuntimeError(f"Snowflake API error ({response.status_code}): {error_msg}")

    res_json = response.json()
    metadata = res_json.get("resultSetMetaData", {})
    col_names = [col.get("name") for col in metadata.get("rowType", [])]
    data_rows = res_json.get("data", [])

    if not col_names or not data_rows:
        return pd.DataFrame()

    raw_df = pd.DataFrame(data_rows, columns=col_names)
    normalized_df = normalize_telemetry_df(raw_df)

    # Filter relative to max date in dataset
    if not normalized_df.empty:
        normalized_df = normalized_df.sort_values("metric_date")
        max_date = normalized_df["metric_date"].max()
        if pd.notna(max_date):
            cutoff_date = max_date - pd.Timedelta(days=lookback_days)
            normalized_df = normalized_df[normalized_df["metric_date"] >= cutoff_date]

    return normalized_df


def is_negative_sentiment_metric(metric_name: str) -> bool:
    """Infers if metric represents an operational risk when it rises."""
    negative_terms = [
        "error", "failure", "fail", "crash", "latency", "bug", "drop",
        "churn", "abandon", "abandonment", "cost", "refund", "ticket",
        "inflow", "surge", "5xx", "4xx", "pool", "usage", "load", "cpu",
        "loss", "incident", "delay", "timeout", "warn"
    ]
    return any(term in metric_name.lower() for term in negative_terms)


def detect_today_anomalies(
    df: pd.DataFrame,
    z_threshold: float = 2.0,
    min_pct_delta: float = 15.0,
) -> Dict[str, List[Dict[str, Any]]]:
    """Detects statistical anomalies across all metrics for the latest day."""
    if df.empty or "metric_name" not in df.columns:
        return {"risks": [], "opportunities": []}

    if "metric_date" not in df.columns or "metric_value" not in df.columns:
        df = normalize_telemetry_df(df)

    risks = []
    opportunities = []

    for metric_name, group in df.groupby("metric_name"):
        sorted_group = group.sort_values("metric_date")
        if len(sorted_group) < 3:
            continue

        historical = sorted_group["metric_value"].iloc[:-1]
        today_val = float(sorted_group["metric_value"].iloc[-1])

        baseline_mean = float(historical.mean())
        baseline_std = float(historical.std(ddof=1)) if len(historical) > 1 else 0.0

        if pd.isna(baseline_mean) or baseline_mean == 0:
            continue

        pct_change = ((today_val - baseline_mean) / abs(baseline_mean)) * 100.0

        if baseline_std > 1e-6:
            z_score = (today_val - baseline_mean) / baseline_std
            is_anomaly = abs(z_score) >= z_threshold and abs(pct_change) >= min_pct_delta
        else:
            z_score = 0.0
            is_anomaly = abs(pct_change) >= max(min_pct_delta, 25.0)

        if not is_anomaly:
            continue

        department = sorted_group["department"].iloc[-1]
        unit = sorted_group["unit"].iloc[-1]

        delta_sign = "+" if pct_change > 0 else ""
        delta_str = f"{delta_sign}{pct_change:.1f}%"

        record = {
            "metric_name": metric_name,
            "current_value": round(today_val, 2) if today_val % 1 != 0 else int(today_val),
            "expected_baseline": round(baseline_mean, 2) if baseline_mean % 1 != 0 else int(baseline_mean),
            "percent_delta": delta_str,
            "z_score": round(float(z_score), 2),
            "unit": unit,
            "department": department,
        }

        is_bad_when_high = is_negative_sentiment_metric(metric_name)
        if (pct_change > 0 and is_bad_when_high) or (pct_change < 0 and not is_bad_when_high):
            risks.append(record)
        else:
            opportunities.append(record)

    risks.sort(key=lambda x: abs(float(x["percent_delta"].replace("%", "").replace("+", ""))), reverse=True)
    opportunities.sort(key=lambda x: abs(float(x["percent_delta"].replace("%", "").replace("+", ""))), reverse=True)

    return {"risks": risks, "opportunities": opportunities}