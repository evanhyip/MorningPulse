# scripts/generate_data.py
import datetime
import os
import numpy as np
import pandas as pd

np.random.seed(42)

DAYS = 60
end_date = datetime.date(2026, 10, 23)
dates = [end_date - datetime.timedelta(days=i) for i in range(DAYS)][::-1]

# 15 enterprise metrics spanning Finance, Growth, Product, Infra, and Support
METRICS_SPEC = [
    # --- Finance & Revenue ---
    {
        "dept": "Finance",
        "name": "daily_net_revenue_usd",
        "base": 125000,
        "std": 6000,
        "unit": "$",
        "direction": "higher_is_better",
        "anomaly": -28000,  # 🚨 Critical Drop (Revenue loss)
    },
    {
        "dept": "Finance",
        "name": "checkout_failure_rate_pct",
        "base": 1.2,
        "std": 0.25,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 4.1,  # 🚨 Critical Spike (Outage)
    },
    {
        "dept": "Finance",
        "name": "refund_request_surge_count",
        "base": 45,
        "std": 8,
        "unit": "req",
        "direction": "lower_is_better",
        "anomaly": 85,  # 🚨 Surge in refund claims
    },
    {
        "dept": "Finance",
        "name": "average_order_value_usd",
        "base": 88.0,
        "std": 3.5,
        "unit": "$",
        "direction": "higher_is_better",
        "anomaly": 0,  # Nominal
    },
    # --- Growth & Marketing ---
    {
        "dept": "Growth",
        "name": "new_user_signups",
        "base": 1200,
        "std": 90,
        "unit": "users",
        "direction": "higher_is_better",
        "anomaly": 650,  # 🚀 Positive Surprise: Viral signup surge
    },
    {
        "dept": "Growth",
        "name": "customer_acquisition_cost_usd",
        "base": 42.0,
        "std": 2.5,
        "unit": "$",
        "direction": "lower_is_better",
        "anomaly": -8.0,  # 🚀 Positive Surprise: CAC dropped significantly
    },
    # --- Product & Engagement ---
    {
        "dept": "Product",
        "name": "daily_active_users",
        "base": 48000,
        "std": 1200,
        "unit": "DAU",
        "direction": "higher_is_better",
        "anomaly": 0,  # Nominal
    },
    {
        "dept": "Product",
        "name": "cart_abandonment_rate_pct",
        "base": 68.5,
        "std": 2.1,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 0,  # Nominal
    },
    {
        "dept": "Product",
        "name": "mobile_app_crash_rate_pct",
        "base": 0.35,
        "std": 0.04,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 0,  # Nominal
    },
    # --- Infrastructure & Reliability ---
    {
        "dept": "Infra",
        "name": "api_latency_p99_ms",
        "base": 210,
        "std": 15,
        "unit": "ms",
        "direction": "lower_is_better",
        "anomaly": 125,  # 🚨 Latency Spike
    },
    {
        "dept": "Infra",
        "name": "http_5xx_server_errors_pct",
        "base": 0.08,
        "std": 0.02,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 0,  # Nominal
    },
    {
        "dept": "Infra",
        "name": "cpu_utilization_cluster_pct",
        "base": 64.0,
        "std": 4.5,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 0,  # Nominal
    },
    {
        "dept": "Infra",
        "name": "database_connection_pool_pct",
        "base": 55.0,
        "std": 5.0,
        "unit": "%",
        "direction": "lower_is_better",
        "anomaly": 0,  # Nominal
    },
    # --- Customer Support ---
    {
        "dept": "Support",
        "name": "ticket_inflow_volume",
        "base": 240,
        "std": 20,
        "unit": "tickets",
        "direction": "lower_is_better",
        "anomaly": 115,  # 🚨 Support ticket surge
    },
    {
        "dept": "Support",
        "name": "csat_customer_satisfaction_pct",
        "base": 94.0,
        "std": 1.2,
        "unit": "%",
        "direction": "higher_is_better",
        "anomaly": 0,  # Nominal
    },
]

rows = []
for d_idx, cur_date in enumerate(dates):
    for m in METRICS_SPEC:
        noise = np.random.normal(0, m["std"])
        val = m["base"] + noise

        # Inject anomalies on the most recent day (2026-10-23)
        if d_idx == DAYS - 1 and m["anomaly"] != 0:
            val += m["anomaly"]

        rows.append(
            {
                "metric_date": cur_date.strftime("%Y-%m-%d"),
                "department": m["dept"],
                "metric_name": m["name"],
                "metric_value": round(float(max(val, 0.0)), 2),
                "unit": m["unit"],
            }
        )

df = pd.DataFrame(rows)

os.makedirs("data", exist_ok=True)
csv_path = "data/seed_metrics.csv"
df.to_csv(csv_path, index=False)
print(f"Generated {len(df)} records across {len(METRICS_SPEC)} metrics at {csv_path}")