import json
import os
import requests
from dotenv import load_dotenv
from core.detector import detect_today_anomalies
from core.logs import get_recent_system_events

load_dotenv()

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_TOKEN = os.getenv("SNOWFLAKE_TOKEN")


# --- 1. EXECUTIVE BRIEF GENERATOR ---
def generate_executive_brief(
    anomalies: list[dict] = None,
    model: str = "llama3.1-8b",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Generates the morning incident brief via Snowflake AI_COMPLETE."""
    if anomalies is None:
        anomalies = detect_today_anomalies()

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

    escaped_prompt = raw_prompt.replace("'", "''")

    url = f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    statement_sql = f"""
        SELECT AI_COMPLETE(
            '{model}',
            '{escaped_prompt}',
            PARSE_JSON('{{"max_tokens": {max_tokens}, "temperature": {temperature}}}')
        ) AS response;
    """
    
    payload = {
        "statement": statement_sql,
        "warehouse": "COMPUTE_WH",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=45)
    response.raise_for_status()

    raw_text = response.json()["data"][0][0]

    try:
        clean_text = json.loads(raw_text)
    except Exception:
        clean_text = raw_text.strip('"').replace(r"\n", "\n")

    return clean_text


# --- 2. INTERACTIVE CHAT AGENT ---
def query_cortex_chat(
    conversation_history: list[dict],
    anomalies: list[dict],
    system_brief: str,
    model: str = "llama3.1-8b",
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Sends chat history and operational context to Snowflake AI_COMPLETE."""
    history_transcript = ""
    for turn in conversation_history[-6:]:
        role = "Executive" if turn["role"] == "user" else "Chief of Staff"
        history_transcript += f"{role}: {turn['content']}\n"

    system_prompt = f"""
You are the AI Chief of Staff in MorningPulse. You previously generated this morning incident brief:
\"\"\"{system_brief}\"\"\"

Known Anomalies: {json.dumps(anomalies)}

Respond concisely and directly to the executive's follow-up inquiries. Quote specific timestamps, systems, and metrics when relevant. Do not hallucinate numbers outside the known data.

CONVERSATION TRANSCRIPT:
{history_transcript}
Chief of Staff:"""

    escaped_prompt = system_prompt.replace("'", "''")

    url = f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    statement_sql = f"""
        SELECT AI_COMPLETE(
            '{model}',
            '{escaped_prompt}',
            PARSE_JSON('{{"max_tokens": {max_tokens}, "temperature": {temperature}}}')
        ) AS response;
    """

    payload = {
        "statement": statement_sql,
        "warehouse": "COMPUTE_WH",
    }

    res = requests.post(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()

    raw_text = res.json()["data"][0][0]
    try:
        return json.loads(raw_text).strip('"')
    except Exception:
        return raw_text.strip('"').replace(r"\n", "\n")


if __name__ == "__main__":
    print("Synthesizing Executive Brief via Snowflake AI_COMPLETE...\n")
    print(generate_executive_brief())