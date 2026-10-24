import json
import pandas as pd


def detect_today_anomalies(
    csv_path: str = "seed_metrics.csv", z_threshold: float = 2.5
) -> list[dict]:
    df = pd.read_csv(csv_path)
    df["metric_date"] = pd.to_datetime(df["metric_date"])
    df = df.sort_values(by=["metric_name", "metric_date"]).reset_index(
        drop=True
    )

    # Calculate 14-day rolling baseline excluding the current day
    df["rolling_avg"] = df.groupby("metric_name")["metric_value"].transform(
        lambda s: s.shift(1).rolling(window=14, min_periods=7).mean()
    )
    df["rolling_std"] = df.groupby("metric_name")["metric_value"].transform(
        lambda s: s.shift(1).rolling(window=14, min_periods=7).std()
    )

    # Compute Z-score
    df["z_score"] = (df["metric_value"] - df["rolling_avg"]) / df[
        "rolling_std"
    ].replace(0, float("nan"))

    # Filter to only the latest date
    latest_date = df["metric_date"].max()
    today_df = df[df["metric_date"] == latest_date].copy()

    # Flag outliers
    outliers = today_df[today_df["z_score"].abs() >= z_threshold]

    anomalies = []
    for _, row in outliers.iterrows():
        pct_change = (
            (row["metric_value"] - row["rolling_avg"]) / row["rolling_avg"]
        ) * 100
        anomalies.append(
            {
                "department": row["department"],
                "metric_name": row["metric_name"],
                "current_value": round(row["metric_value"], 2),
                "expected_baseline": round(row["rolling_avg"], 2),
                "percent_delta": f"{pct_change:+.1f}%",
                "z_score": round(row["z_score"], 2),
                "unit": row["unit"],
            }
        )

    return anomalies


if __name__ == "__main__":
    results = detect_today_anomalies()
    print(
        f"Detected {len(results)} anomalies for the morning brief:\n"
    )
    print(json.dumps(results, indent=2))