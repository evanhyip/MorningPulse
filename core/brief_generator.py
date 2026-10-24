"""
core/brief_generator.py
Synthesizes executive daily briefings and powers the AI Chief of Staff
using Snowflake AI_COMPLETE. Fully supports dynamic schema/table configuration.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import requests

load_dotenv()


def get_snowflake_config() -> Dict[str, str]:
    """Resolves database, schema, and warehouse coordinates dynamically."""
    return {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "token": os.getenv("SNOWFLAKE_TOKEN", ""),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(' "\''),
        "database": os.getenv("SNOWFLAKE_DATABASE", "MORNINGPULSE_DB").strip(' "\''),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "TELEMETRY").strip(' "\''),
    }


def execute_snowflake_query(sql: str) -> List[List[Any]]:
    """Executes a SQL statement via the Snowflake Statements API."""
    cfg = get_snowflake_config()
    if not cfg["account"] or not cfg["token"]:
        raise ValueError("Missing SNOWFLAKE_ACCOUNT or SNOWFLAKE_TOKEN in environment.")

    url = f"https://{cfg['account']}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "statement": sql,
        "warehouse": cfg["warehouse"],
        "database": cfg["database"],
        "schema": cfg["schema"],
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        error_msg = response.json().get("message", response.text)
        raise RuntimeError(f"Snowflake API error ({response.status_code}): {error_msg}")

    return response.json().get("data", [])


def clean_llm_response(raw_text: str) -> str:
    """Decodes double-encoded JSON string literals from the Snowflake REST response."""
    if not isinstance(raw_text, str):
        return str(raw_text)

    text = raw_text.strip()
    if (text.startswith('"') and text.endswith('"')) or "\\n" in text:
        try:
            return json.loads(text)
        except Exception:
            pass
    return text


def format_anomalies_for_prompt(anomalies: Dict[str, List[Dict[str, Any]]]) -> str:
    """Formats detected risks and opportunities into structured context for the LLM."""
    risks = anomalies.get("risks", [])
    opps = anomalies.get("opportunities", [])

    lines = ["### CRITICAL OPERATIONAL RISKS:"]
    if risks:
        for r in risks:
            unit = r.get("unit", "")
            lines.append(
                f"- [{r.get('department', 'General')}] {r['metric_name']}: "
                f"Current {r['current_value']}{unit} vs Baseline {r['expected_baseline']}{unit} "
                f"({r['percent_delta']}, Z-Score: {r['z_score']})"
            )
    else:
        lines.append("- No critical risks detected today.")

    lines.append("\n### POSITIVE MOMENTUM & GROWTH OPPORTUNITIES:")
    if opps:
        for o in opps:
            unit = o.get("unit", "")
            lines.append(
                f"- [{o.get('department', 'General')}] {o['metric_name']}: "
                f"Current {o['current_value']}{unit} vs Baseline {o['expected_baseline']}{unit} "
                f"({o['percent_delta']}, Z-Score: {o['z_score']})"
            )
    else:
        lines.append("- No notable positive deviations detected today.")

    return "\n".join(lines)


def generate_executive_brief(
    anomalies: Dict[str, List[Dict[str, Any]]],
    model: str = "llama3.1-70b",
    max_tokens: int = 768,
    temperature: float = 0.2,
) -> str:
    """Generates the executive morning briefing via Snowflake AI_COMPLETE."""
    context = format_anomalies_for_prompt(anomalies)

    prompt = f"""You are the Chief of Staff to the CEO of a high-growth enterprise.
Analyze the following statistical anomalies detected in today's telemetry:

{context}

Provide a crisp, actionable executive morning briefing organized into 3 sections:
1. Executive Triage (2-3 sentences on the most critical operational risk and potential root causes)
2. Departmental Escalations (Bullet points indicating which team leads must act today and why)
3. Strategic Upside (1-2 sentences highlighting positive signals to lean into)

Tone: Authoritative, calm, operationally specific. Do not use generic filler phrases.
"""
    sanitized_prompt = prompt.replace("'", "''")
    sql = f"SELECT AI_COMPLETE('{model}', '{sanitized_prompt}') AS BRIEF;"

    rows = execute_snowflake_query(sql)
    if rows and len(rows[0]) > 0 and rows[0][0]:
        return clean_llm_response(rows[0][0])

    return "Unable to generate executive brief from telemetry."


def query_cortex_chat(
    conversation_history: List[Dict[str, str]],
    anomalies: List[Dict[str, Any]],
    system_brief: str = "",
    model: str = "llama3.1-70b",
    max_tokens: int = 768,
    temperature: float = 0.2,
) -> str:
    """Interactive conversational agent for sidebar chat in app.py."""
    last_query = conversation_history[-1]["content"] if conversation_history else ""

    history_str = ""
    for msg in conversation_history[-6:-1]:
        history_str += f"{msg['role'].upper()}: {msg['content']}\n"

    full_prompt = f"""You are the AI Chief of Staff answering an executive's questions about today's telemetry.
Current Executive Briefing:
{system_brief}

Detected Anomalies:
{anomalies}

Recent Conversation:
{history_str}

Executive Question: {last_query}

Provide a direct, concise, and mathematically grounded response.
"""
    sanitized_prompt = full_prompt.replace("'", "''")
    sql = f"SELECT AI_COMPLETE('{model}', '{sanitized_prompt}') AS ANSWER;"

    rows = execute_snowflake_query(sql)
    if rows and len(rows[0]) > 0 and rows[0][0]:
        return clean_llm_response(rows[0][0])

    return "No response generated."


# =====================================================================
# Snowflake Briefing Persistence (Dynamic Cache)
# =====================================================================

def get_latest_cached_brief() -> Optional[Dict[str, Any]]:
    """Retrieves the latest cached executive brief from DAILY_BRIEFS."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."DAILY_BRIEFS"'
    sql = f"""
        SELECT brief_text, TO_VARCHAR(created_at, 'YYYY-MM-DD HH24:MI:SS'), sent_via_email
        FROM {table}
        ORDER BY created_at DESC
        LIMIT 1;
    """
    try:
        rows = execute_snowflake_query(sql)
        if rows and len(rows[0]) > 0 and rows[0][0]:
            return {
                "text": clean_llm_response(rows[0][0]),
                "updated_at": str(rows[0][1]) if len(rows[0]) > 1 else "Database",
                "sent_via_email": bool(rows[0][2]) if len(rows[0]) > 2 else False,
            }
    except Exception:
        # Fallback if sent_via_email column is not present
        try:
            sql_fallback = f"SELECT brief_text, TO_VARCHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') FROM {table} ORDER BY created_at DESC LIMIT 1;"
            rows = execute_snowflake_query(sql_fallback)
            if rows and len(rows[0]) > 0 and rows[0][0]:
                return {
                    "text": clean_llm_response(rows[0][0]),
                    "updated_at": str(rows[0][1]) if len(rows[0]) > 1 else "Database",
                    "sent_via_email": False,
                }
        except Exception:
            return None
    return None


def save_brief_to_snowflake(brief_text: str, sent_via_email: bool = False) -> bool:
    """Saves a newly synthesized briefing to DAILY_BRIEFS."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."DAILY_BRIEFS"'
    today_str = datetime.today().strftime("%Y-%m-%d")
    sanitized_text = brief_text.replace("'", "''")

    sql = f"""
        INSERT INTO {table} (brief_date, brief_text, created_at, sent_via_email)
        SELECT '{today_str}', '{sanitized_text}', CURRENT_TIMESTAMP(), {str(sent_via_email).upper()};
    """
    try:
        execute_snowflake_query(sql)
        return True
    except Exception:
        # Fallback if table doesn't have sent_via_email column
        try:
            sql_fallback = f"""
                INSERT INTO {table} (brief_date, brief_text, created_at)
                SELECT '{today_str}', '{sanitized_text}', CURRENT_TIMESTAMP();
            """
            execute_snowflake_query(sql_fallback)
            return True
        except Exception:
            return False


# =====================================================================
# Mailing List Management
# =====================================================================

def upsert_subscriber(email: str, full_name: str, role: str, is_active: bool = True) -> bool:
    """Inserts or updates a recipient in MAILING_LIST dynamically."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."MAILING_LIST"'

    clean_email = email.strip().lower().replace("'", "''")
    clean_name = full_name.strip().replace("'", "''")
    clean_role = role.strip().replace("'", "''")

    sql = f"""
        MERGE INTO {table} AS target
        USING (SELECT '{clean_email}' AS email) AS src
        ON LOWER(target.email) = src.email
        WHEN MATCHED THEN
            UPDATE SET full_name = '{clean_name}', role = '{clean_role}', is_active = {str(is_active).upper()}
        WHEN NOT MATCHED THEN
            INSERT (email, full_name, role, is_active, subscribed_at)
            VALUES ('{clean_email}', '{clean_name}', '{clean_role}', {str(is_active).upper()}, CURRENT_TIMESTAMP());
    """
    try:
        execute_snowflake_query(sql)
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to upsert subscriber: {e}")


import pandas as pd


def get_active_mailing_list() -> List[str]:
    """
    Returns a list of active recipient email addresses from MAILING_LIST.
    Used by scripts/dispatch_morning_pulse.py for automated dispatches.
    """
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."MAILING_LIST"'
    sql = f"""
        SELECT email 
        FROM {table} 
        WHERE is_active = TRUE;
    """
    try:
        rows = execute_snowflake_query(sql)
        return [str(r[0]).strip() for r in rows if r and r[0]]
    except Exception as e:
        print(f"Error fetching active mailing list: {e}")
        return []


def get_all_subscribers_df() -> pd.DataFrame:
    """
    Returns the full subscriber directory as a DataFrame for app.py display.
    """
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."MAILING_LIST"'
    sql = f"""
        SELECT full_name, email, role, is_active
        FROM {table}
        ORDER BY subscribed_at DESC;
    """
    try:
        rows = execute_snowflake_query(sql)
        if not rows:
            return pd.DataFrame(columns=["full_name", "email", "role", "is_active"])
        return pd.DataFrame(
            rows, 
            columns=["full_name", "email", "role", "is_active"]
        )
    except Exception as e:
        print(f"Error fetching subscriber dataframe: {e}")
        return pd.DataFrame(columns=["full_name", "email", "role", "is_active"])