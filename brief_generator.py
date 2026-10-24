import json
import os
from detector import detect_today_anomalies
from dotenv import load_dotenv
from logs import get_recent_system_events
import requests

load_dotenv()

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_TOKEN = os.getenv("SNOWFLAKE_TOKEN")


def generate_executive_brief() -> str:
    anomalies = detect_today_anomalies("seed_metrics.csv")
    events = get_recent_system_events()

    raw_prompt = f"""
You are the autonomous Chief of Staff delivering the 8:00 AM Executive Pulse.

METRIC ANOMALIES DETECTED IN SNOWFLAKE:
{json.dumps(anomalies, indent=2)}

RECENT SYSTEM LOGS & DEPLOYMENTS:
{json.dumps(events, indent=2)}

Analyze the anomalies against the system logs. Connect the causal dots.

Provide your response in clean Markdown with these exact sections:
### 1. Executive Summary
A 2-sentence synthesis explaining the primary operational failure and its direct business consequence.

### 2. Root Cause & Smoking Gun
Quote the specific deployment, error message, and timestamp responsible.

### 3. Business Impact
Summarize the estimated financial or operational damage based on the numbers.

### 4. Autonomous Action Plan
Provide 3 immediate checklist items for engineering and customer operations.
"""

    # Escape single quotes for Snowflake SQL string literal
    escaped_prompt = raw_prompt.replace("'", "''")

    url = f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "statement": f"SELECT AI_COMPLETE('llama3.1-8b', '{escaped_prompt}') AS response;",
        "warehouse": "COMPUTE_WH",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=45)
    response.raise_for_status()

    return response.json()["data"][0][0]


if __name__ == "__main__":
    print("Synthesizing Executive Brief via Snowflake AI_COMPLETE...\n")
    print(generate_executive_brief())