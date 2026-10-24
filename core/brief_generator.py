"""
core/brief_generator.py
Synthesizes executive daily briefings and powers the AI Chief of Staff
using Snowflake AI_COMPLETE. Dynamic schema/table support with original formatting preserved.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import requests

load_dotenv()


def get_snowflake_config() -> Dict[str, str]:
    """Resolves database and warehouse configuration dynamically."""
    return {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "token": os.getenv("SNOWFLAKE_TOKEN", ""),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(' "\''),
        "database": os.getenv("SNOWFLAKE_DATABASE", "MORNINGPULSE_DB").strip(' "\''),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "TELEMETRY").strip(' "\''),
    }


def execute_snowflake_query(sql: str) -> List[List[Any]]:
    """Executes a query via the Snowflake Statements API."""
    cfg = get_snowflake_config()
    if not cfg["account"] or not cfg["token"]:
        raise ValueError("Missing SNOWFLAKE_ACCOUNT or SNOWFLAKE_TOKEN.")

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


def format_anomalies_for_prompt(anomalies: Dict[str, List[Dict[str, Any]]]) -> str:
    """Formats detected anomalies into prompt context."""
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


def generate_executive_brief(
    anomalies: Dict[str, List[Dict[str, Any]]],
    model: str = "llama3.1-70b",
) -> str:
    """Generates the executive morning briefing via AI_COMPLETE."""
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


def ask_chief_of_staff(
    user_query: str,
    context: str = "",
    model: str = "llama3.1-70b",
) -> str:
    """Interactive conversational agent grounded in telemetry context."""
    full_prompt = f"""You are the Chief of Staff answering an executive's questions about today's telemetry and briefing.
Context:
{context}

Executive Question: {user_query}

Provide a direct, concise, and mathematically grounded response.
"""
    sanitized_prompt = full_prompt.replace("'", "''")
    sql = f"SELECT AI_COMPLETE('{model}', '{sanitized_prompt}') AS ANSWER;"

    rows = execute_snowflake_query(sql)
    if rows and len(rows[0]) > 0 and rows[0][0]:
        return clean_llm_response(rows[0][0])

    return "No response generated."


def get_cached_brief_for_today(target_date: Optional[str] = None) -> Optional[str]:
    """Retrieves cached briefing from the dynamic DAILY_BRIEFS table."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."DAILY_BRIEFS"'
    date_str = target_date or datetime.today().strftime("%Y-%m-%d")

    sql = f"SELECT brief_text FROM {table} WHERE brief_date = '{date_str}' ORDER BY created_at DESC LIMIT 1;"
    try:
        rows = execute_snowflake_query(sql)
        if rows and len(rows[0]) > 0 and rows[0][0]:
            return clean_llm_response(rows[0][0])
    except Exception:
        return None
    return None


def save_brief_to_cache(brief_text: str, target_date: Optional[str] = None) -> bool:
    """Persists a generated briefing into DAILY_BRIEFS."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."DAILY_BRIEFS"'
    date_str = target_date or datetime.today().strftime("%Y-%m-%d")
    sanitized_text = brief_text.replace("'", "''")

    sql = f"""
    INSERT INTO {table} (brief_date, brief_text, created_at)
    SELECT '{date_str}', '{sanitized_text}', CURRENT_TIMESTAMP();
    """
    try:
        execute_snowflake_query(sql)
        return True
    except Exception:
        return False


def fetch_mailing_list() -> List[Dict[str, str]]:
    """Retrieves active subscribers from the dynamic MAILING_LIST table."""
    cfg = get_snowflake_config()
    table = f'"{cfg["database"]}"."{cfg["schema"]}"."MAILING_LIST"'
    sql = f"SELECT email, full_name, role, is_active FROM {table} WHERE is_active = TRUE;"

    try:
        rows = execute_snowflake_query(sql)
        return [
            {
                "email": str(r[0]),
                "name": str(r[1]) if len(r) > 1 else "",
                "role": str(r[2]) if len(r) > 2 else "Stakeholder",
            }
            for r in rows
        ]
    except Exception:
        return []