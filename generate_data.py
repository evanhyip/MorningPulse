from datetime import date, timedelta
import random
import pandas as pd

# Define departments, metrics, baseline means, standard deviations, and units
metrics = [
    ("Payments", "checkout_failure_rate_pct", 0.4, 0.05, "%"),
    ("Growth", "daily_active_users", 45000, 1200, "count"),
    ("Finance", "daily_refund_volume_usd", 1800, 200, "USD"),
    ("Infrastructure", "p99_latency_ms", 120, 15, "ms"),
    ("Customer Ops", "support_ticket_backlog", 85, 10, "tickets"),
]

rows = []
base_date = date.today() - timedelta(days=60)

for day in range(60):
    current_date = base_date + timedelta(days=day)
    for dept, name, mean, std, unit in metrics:
        val = max(0.0, random.gauss(mean, std))

        # Plant anomalies on the most recent day (today)
        if day == 59:
            if name == "checkout_failure_rate_pct":
                val = 4.85  # Baseline is ~0.40%
            elif name == "daily_refund_volume_usd":
                val = 8400.0  # Baseline is ~$1,800.00

        rows.append(
            {
                "metric_date": current_date.strftime("%Y-%m-%d"),
                "department": dept,
                "metric_name": name,
                "metric_value": round(val, 2),
                "unit": unit,
            }
        )

df = pd.DataFrame(rows)
df.to_csv("seed_metrics.csv", index=False)
print("Saved 60 days of telemetry to seed_metrics.csv")