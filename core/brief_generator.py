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
    anomalies: dict[str, list[dict]] | list[dict] | None = None,
    model: str = "llama3.1-8b",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Generates an executive briefing covering both operational risks and growth opportunities."""
    if anomalies is None:
        anomalies = detect_today_anomalies()

    # Normalize structure if passed as a flat list
    if isinstance(anomalies, list):
        risks = [a for a in anomalies if a.get("type") == "risk"]
        opportunities = [a for a in anomalies if a.get("type") == "opportunity"]
    else:
        risks = anomalies.get("risks", [])
        opportunities = anomalies.get("opportunities", [])

    events = get_recent_system_events()

    raw_prompt = f"""
You are the autonomous Chief of Staff delivering the 8:00 AM Executive Pulse.

CRITICAL OPERATIONAL RISKS:
{json.dumps(risks, indent=2)}

POSITIVE GROWTH OPPORTUNITIES & SURGES:
{json.dumps(opportunities, indent=2)}

RECENT SYSTEM LOGS & DEPLOYMENTS:
{json.dumps(events, indent=2)}

Analyze the operational failures against the system deployments, but also highlight any notable growth windfalls. Connect the causal dots across engineering, finance, and product.

Provide your response in clean Markdown with these exact sections:
### 1. Executive Summary
A 2-sentence synthesis explaining the primary operational crisis and any counterbalancing growth wins.

### 2. Root Cause & Smoking Gun
Quote the specific deployment, error message, and timestamp responsible for the failures.

### 3. Business Impact & Exposure
Detail estimated revenue loss, refund surge, and support ticket pressure alongside customer acquisition wins.

### 4. Autonomous Action Plan
Provide 3 immediate checklist items for engineering rollback and customer operations triage.
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
    anomalies: dict[str, list[dict]] | list[dict],
    system_brief: str,
    model: str = "llama3.1-8b",
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Sends chat history and dual-threat telemetry context to Snowflake AI_COMPLETE."""
    history_transcript = ""
    for turn in conversation_history[-6:]:
        role = "Executive" if turn["role"] == "user" else "Chief of Staff"
        history_transcript += f"{role}: {turn['content']}\n"

    system_prompt = f"""
You are the AI Chief of Staff in MorningPulse. You previously generated this morning brief:
\"\"\"{system_brief}\"\"\"

Telemetry Outliers:
{json.dumps(anomalies)}

Respond concisely and directly to executive inquiries regarding root causes, financial damage, customer acquisition, or staged rollbacks. Do not hallucinate numbers outside the known data.

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
    print("Testing Snowflake Cortex synthesis with directional anomalies...\n")
    print(generate_executive_brief())


# In core/brief_generator.py


def get_latest_cached_brief() -> dict | None:
    """Retrieves the most recent synthesized brief from Snowflake storage."""
    url = (
        f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    )
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    sql = """
        SELECT 
            TO_VARCHAR(brief_date, 'YYYY-MM-DD') AS brief_date,
            brief_text,
            TO_VARCHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
            sent_via_email
        FROM MORNINGPULSE_DB.TELEMETRY.DAILY_BRIEFS
        ORDER BY brief_date DESC, updated_at DESC
        LIMIT 1;
    """
    payload = {"statement": sql, "warehouse": "COMPUTE_WH"}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        rows = res.json().get("data", [])
        if not rows:
            return None

        row = rows[0]
        return {
            "date": row[0],
            "text": row[1],
            "updated_at": row[2],
            "sent_via_email": str(row[3]).lower() == "true",
        }
    except Exception as e:
        print(f"Warning: Failed to read cached brief from Snowflake: {e}")
        return None


def save_brief_to_snowflake(
    brief_text: str, sent_via_email: bool = False
) -> None:
    """Upserts the briefing into Snowflake for today's date."""
    url = (
        f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
    )
    headers = {
        "Authorization": f"Bearer {SNOWFLAKE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    escaped_text = brief_text.replace("'", "''")
    email_flag = "TRUE" if sent_via_email else "FALSE"

    # Merge/upsert on today's date
    sql = f"""
        MERGE INTO MORNINGPULSE_DB.TELEMETRY.DAILY_BRIEFS AS target
        USING (
            SELECT 
                CURRENT_DATE() AS brief_date, 
                '{escaped_text}' AS brief_text,
                {email_flag} AS sent_via_email
        ) AS src
        ON target.brief_date = src.brief_date
        WHEN MATCHED THEN
            UPDATE SET 
                target.brief_text = src.brief_text, 
                target.updated_at = CURRENT_TIMESTAMP(),
                target.sent_via_email = src.sent_via_email
        WHEN NOT MATCHED THEN
            INSERT (brief_date, brief_text, sent_via_email) 
            VALUES (src.brief_date, src.brief_text, src.sent_via_email);
    """
    payload = {"statement": sql, "warehouse": "COMPUTE_WH"}

    res = requests.post(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()