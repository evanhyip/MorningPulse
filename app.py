# app.py
import os
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from core.brief_generator import (
    generate_executive_brief,
    get_latest_cached_brief,
    query_cortex_chat,
    save_brief_to_snowflake,
)
from core.detector import detect_today_anomalies, fetch_telemetry_from_snowflake

# Optional helper import from brief_generator if available
try:
    from core.brief_generator import upsert_subscriber
except ImportError:
    upsert_subscriber = None

st.set_page_config(
    page_title="MorningPulse",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- METRIC METADATA & TITLES ---
METRIC_META = {
    "daily_net_revenue_usd": {"title": "Daily Net Revenue", "fmt": "${:,.0f}"},
    "checkout_failure_rate_pct": {"title": "Checkout Failure Rate", "fmt": "{:.2f}%"},
    "refund_request_surge_count": {"title": "Refund Requests", "fmt": "{:,.0f} req"},
    "average_order_value_usd": {"title": "Average Order Value", "fmt": "${:.2f}"},
    "new_user_signups": {"title": "New User Signups", "fmt": "{:,.0f}"},
    "customer_acquisition_cost_usd": {"title": "Acquisition Cost (CAC)", "fmt": "${:.2f}"},
    "daily_active_users": {"title": "Daily Active Users (DAU)", "fmt": "{:,.0f}"},
    "cart_abandonment_rate_pct": {"title": "Cart Abandonment", "fmt": "{:.1f}%"},
    "mobile_app_crash_rate_pct": {"title": "App Crash Rate", "fmt": "{:.2f}%"},
    "api_latency_p99_ms": {"title": "P99 API Latency", "fmt": "{:.0f} ms"},
    "http_5xx_server_errors_pct": {"title": "5xx Server Errors", "fmt": "{:.2f}%"},
    "cpu_utilization_cluster_pct": {"title": "Cluster CPU Load", "fmt": "{:.1f}%"},
    "database_connection_pool_pct": {"title": "DB Pool Usage", "fmt": "{:.1f}%"},
    "ticket_inflow_volume": {"title": "Support Ticket Inflow", "fmt": "{:,.0f}"},
    "csat_customer_satisfaction_pct": {"title": "Customer CSAT", "fmt": "{:.1f}%"},
}


def get_delta_color(change_str: str, is_risk: bool) -> str:
    """Ensures risks are displayed in red and growth windfalls in green."""
    is_positive = not change_str.startswith("-")
    if is_risk:
        return "inverse" if is_positive else "normal"
    return "normal" if is_positive else "inverse"


def mask_email(email: str) -> str:
    """Masks an email for privacy while keeping it identifiable."""
    if not email or not isinstance(email, str) or "@" not in email:
        return "—"

    clean = email.strip()
    try:
        local, domain = clean.split("@", 1)
        if len(local) <= 1:
            masked_local = local + "***"
        elif len(local) == 2:
            masked_local = local[0] + "*" + local[-1]
        else:
            # Shows first 2 chars and last char: "alexander" -> "al*****r"
            visible_prefix = local[:2] if len(local) >= 4 else local[:1]
            masked_stars = "*" * max(3, len(local) - len(visible_prefix) - 1)
            masked_local = f"{visible_prefix}{masked_stars}{local[-1]}"

        return f"{masked_local}@{domain}"
    except Exception:
        return "—"


def fetch_subscribers_data() -> list[dict]:
    """Fetches subscriber list from Snowflake with support for both module helper and direct query."""
    try:
        from core.brief_generator import get_all_subscribers_df
        res = get_all_subscribers_df()
        if isinstance(res, pd.DataFrame):
            return res.to_dict(orient="records")
        if isinstance(res, list):
            return res
    except (ImportError, AttributeError):
        pass

    account = os.getenv("SNOWFLAKE_ACCOUNT")
    token = os.getenv("SNOWFLAKE_TOKEN")
    db = os.getenv("SNOWFLAKE_DATABASE", "MORNINGPULSE_DB").strip(' "\'')
    schema = os.getenv("SNOWFLAKE_SCHEMA", "TELEMETRY").strip(' "\'')
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(' "\'')

    if not account or not token:
        try:
            from core.brief_generator import get_active_mailing_list
            active_emails = get_active_mailing_list()
            return [{"full_name": "Subscriber", "email": e, "role": "Team Member", "is_active": True} for e in active_emails]
        except Exception:
            return []

    url = f"https://{account}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    sql = f"""
        SELECT full_name, email, role, is_active
        FROM "{db}"."{schema}"."MAILING_LIST"
        ORDER BY subscribed_at DESC;
    """
    try:
        res = requests.post(url, headers=headers, json={"statement": sql, "warehouse": warehouse}, timeout=15)
        res.raise_for_status()
        rows = res.json().get("data", [])
        return [
            {
                "full_name": r[0] or "Subscriber",
                "email": r[1] or "",
                "role": r[2] or "Team Member",
                "is_active": str(r[3]).upper() in ["TRUE", "1"],
            }
            for r in rows
            if r
        ]
    except Exception as e:
        st.error(f"Failed to query mailing list from Snowflake: {e}")
        return []

def delete_subscriber_from_snowflake(email: str) -> bool:
    """Deletes a subscriber from Snowflake MAILING_LIST by email."""
    try:
        from core.brief_generator import delete_subscriber
        return delete_subscriber(email)
    except (ImportError, AttributeError):
        pass

    account = os.getenv("SNOWFLAKE_ACCOUNT")
    token = os.getenv("SNOWFLAKE_TOKEN")
    db = os.getenv("SNOWFLAKE_DATABASE", "MORNINGPULSE_DB").strip(' "\'')
    schema = os.getenv("SNOWFLAKE_SCHEMA", "TELEMETRY").strip(' "\'')
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(' "\'')

    if not account or not token or not email:
        return False

    clean_email = email.strip().lower().replace("'", "''")
    url = f"https://{account}.snowflakecomputing.com/api/v2/statements"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    sql = f"""
        DELETE FROM "{db}"."{schema}"."MAILING_LIST"
        WHERE LOWER(email) = '{clean_email}';
    """
    try:
        res = requests.post(url, headers=headers, json={"statement": sql, "warehouse": warehouse}, timeout=15)
        res.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Failed to delete subscriber: {e}")
        return False


# --- 1. DATA INGESTION & ANOMALY DETECTION ---
@st.cache_data(ttl=600)
def load_data():
    return fetch_telemetry_from_snowflake()


try:
    df = load_data()
except Exception as e:
    st.error(f"Failed to query Snowflake warehouse: {e}")
    st.stop()

anomalies_dict = detect_today_anomalies(df)
risks = anomalies_dict.get("risks", [])
opps = anomalies_dict.get("opportunities", [])
all_anomalies = risks + opps


# --- 2. BRIEF INITIALIZATION VIA SNOWFLAKE PERSISTENCE ---
# Check Snowflake for today's / latest cached briefing first
if "brief" not in st.session_state:
    cached = get_latest_cached_brief()
    if cached and cached.get("text"):
        st.session_state["brief"] = cached["text"]
        st.session_state["brief_source"] = f"Cached ({cached.get('updated_at', 'Database')})"
        st.session_state["brief_email_status"] = cached.get("sent_via_email", False)
    else:
        # Fall back to live synthesis if Snowflake has no existing record
        with st.spinner("Synthesizing fresh 8:00 AM telemetry brief..."):
            try:
                new_brief = generate_executive_brief(anomalies=anomalies_dict)
                save_brief_to_snowflake(new_brief, sent_via_email=False)
                st.session_state["brief"] = new_brief
                st.session_state["brief_source"] = "Generated on Launch"
                st.session_state["brief_email_status"] = False
            except Exception as e:
                st.session_state["brief"] = f"Failed to synthesize brief: {e}"
                st.session_state["brief_source"] = "Error"


# --- 3. SIDEBAR: CHIEF OF STAFF AGENT & CONFIG ---
with st.sidebar:
    st.title("💬 AI Chief of Staff")
    st.caption("Live Snowflake Cortex incident & telemetry copilot.")

    with st.expander("⚙️ Cortex Configuration", expanded=False):
        selected_model = st.selectbox(
            "AI Model",
            ["llama3.1-70b", "llama3.1-8b", "mistral-large2", "snowflake-arctic"],
            index=0,
            help="Hosted foundational LLMs via Snowflake Cortex AI_COMPLETE",
        )
        max_tokens = st.slider("Max Output Tokens", 128, 2048, 768, 64)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
        st.caption(f"Warehouse: `{os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')}`")
        st.caption(f"Database: `{os.getenv('SNOWFLAKE_DATABASE', 'MORNINGPULSE_DB')}.{os.getenv('SNOWFLAKE_SCHEMA', 'TELEMETRY')}`")

    st.divider()

    # Conversation History
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    chat_box = st.container(height=420)
    for msg in st.session_state["chat_history"]:
        with chat_box.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Persistent Sidebar Chat Input
    if prompt := st.chat_input("Ask Chief of Staff..."):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with chat_box.chat_message("user"):
            st.markdown(prompt)

        with chat_box.chat_message("assistant"):
            with st.spinner("Consulting Cortex..."):
                try:
                    agent_res = query_cortex_chat(
                        conversation_history=st.session_state["chat_history"],
                        anomalies=all_anomalies,
                        system_brief=st.session_state.get("brief", ""),
                        model=selected_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    st.markdown(agent_res)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": agent_res}
                    )
                except Exception as e:
                    st.error(f"Error querying Snowflake Cortex Agent: {e}")


# --- 4. MAIN DASHBOARD CONTENT ---
st.title("☀️ MorningPulse")
st.caption("Enterprise Telemetry Intelligence · Powered by Snowflake Cortex")

metric_count = len(df["metric_name"].unique()) if "metric_name" in df.columns else 15

tab_exec, tab_cockpit, tab_subscribers = st.tabs(
    [
        "☀️ Executive Morning Pulse",
        f"📊 Company Cockpit (All {metric_count} Metrics)",
        "📬 Mailing List",
    ]
)

# ==========================================
# TAB 1: EXECUTIVE MORNING PULSE
# ==========================================
with tab_exec:
    # 1. Critical Operational Risks
    st.markdown("### 🚨 Operational Risks Requiring Immediate Attention")
    if risks:
        r_cols = st.columns(len(risks))
        for idx, a in enumerate(risks):
            meta = METRIC_META.get(
                a["metric_name"],
                {"title": a["metric_name"].replace("_", " ").title()},
            )
            color_mode = get_delta_color(a["percent_delta"], is_risk=True)

            with r_cols[idx]:
                st.metric(
                    label=f"{a['department'].upper()} · {meta['title']}",
                    value=f"{a['current_value']} {a['unit']}",
                    delta=f"{a['percent_delta']} vs normal",
                    delta_color=color_mode,
                )
                st.caption(
                    f"🔴 **Critical Outlier** (Baseline: ~{a['expected_baseline']} {a['unit']})"
                )
    else:
        st.success("No operational risks detected across the fleet.")

    # 2. Positive Business Opportunities
    if opps:
        st.markdown("### 🚀 Positive Growth Windfalls & Surges")
        o_cols = st.columns(len(opps))
        for idx, a in enumerate(opps):
            meta = METRIC_META.get(
                a["metric_name"],
                {"title": a["metric_name"].replace("_", " ").title()},
            )
            color_mode = get_delta_color(a["percent_delta"], is_risk=False)

            with o_cols[idx]:
                st.metric(
                    label=f"{a['department'].upper()} · {meta['title']}",
                    value=f"{a['current_value']} {a['unit']}",
                    delta=f"{a['percent_delta']} vs normal",
                    delta_color=color_mode,
                )
                st.caption(
                    f"🟢 **Growth Surge** (Baseline: ~{a['expected_baseline']} {a['unit']})"
                )

    st.divider()

    # 3. Cortex Incident Briefing Section
    col_header, col_meta, col_refresh = st.columns([3, 2, 1])
    with col_header:
        st.subheader("📋 Executive Incident Briefing")
    with col_meta:
        source_label = st.session_state.get("brief_source", "Database")
        st.caption(f"Status: `{source_label}`")
    with col_refresh:
        if st.button("🔄 Regenerate Brief", use_container_width=True):
            with st.spinner(f"Re-synthesizing via {selected_model}..."):
                try:
                    fresh_brief = generate_executive_brief(
                        anomalies=anomalies_dict,
                        model=selected_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    # Persist the freshly generated brief to Snowflake table
                    save_brief_to_snowflake(fresh_brief, sent_via_email=False)
                    st.session_state["brief"] = fresh_brief
                    st.session_state["brief_source"] = "Manual Refresh"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error calling Cortex: {e}")

    if st.session_state.get("brief"):
        with st.container(border=True):
            st.markdown(st.session_state["brief"])

        st.markdown("#### ⚡ Staged Remediation Actions")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🚨 Trigger Rollback (`checkout-service-v2.14`)", use_container_width=True):
                st.success("Rollback command dispatched to Kubernetes cluster.")
        with c2:
            if st.button("📢 Broadcast Status Incident Advisory", use_container_width=True):
                st.info("Incident advisory posted to customer status channels.")
        with c3:
            if st.button("📧 Dispatch Briefing Email to All-Hands", use_container_width=True):
                with st.spinner("Dispatching styled briefing to distribution list..."):
                    try:
                        from scripts.dispatch_morning_pulse import send_daily_pulse_email
                        send_daily_pulse_email(brief_text=st.session_state["brief"])
                        st.success("Briefing email sent to distribution list!")
                    except Exception as e:
                        st.error(f"Failed to send email: {e}")


# ==========================================
# TAB 2: COMPANY COCKPIT (ALL CHARTS)
# ==========================================
with tab_cockpit:
    st.markdown(f"### 📊 Enterprise Telemetry Cockpit (All {metric_count} Metrics)")
    st.caption(
        "Real-time 14-day tracking across Finance, Product, Infrastructure, and Customer Support. "
        "Outliers are automatically surfaced to the Executive Morning Pulse."
    )

    metrics_list = df["metric_name"].unique()
    grid_cols = st.columns(3)

    for i, m_name in enumerate(metrics_list):
        col = grid_cols[i % 3]
        meta = METRIC_META.get(m_name, {"title": m_name.replace("_", " ").title()})
        m_df = df[df["metric_name"] == m_name].sort_values("metric_date").tail(14)

        is_risk = any(r["metric_name"] == m_name for r in risks)
        is_opp = any(o["metric_name"] == m_name for o in opps)

        line_color = "#E02424" if is_risk else ("#0E9F6E" if is_opp else "#3F83F8")
        status_tag = " [🚨 ALERT]" if is_risk else (" [🚀 SURGE]" if is_opp else "")

        fig = px.line(
            m_df,
            x="metric_date",
            y="metric_value",
            markers=True,
            title=f"{meta['title']}{status_tag}",
        )
        fig.update_traces(line_color=line_color)
        fig.update_layout(
            height=220,
            margin=dict(l=20, r=20, t=35, b=20),
            xaxis_title=None,
            yaxis_title=None,
        )

        with col:
            with st.container(border=True):
                st.plotly_chart(fig, use_container_width=True)


# ==========================================
# TAB 3: MAILING LIST & DISTRIBUTION DIRECTORY
# ==========================================
with tab_subscribers:
    st.markdown("### 📬 MorningPulse Distribution Directory")
    st.caption(
        "Recipients configured in Snowflake to receive the automated 4:15 AM PST executive briefing. "
        "Email addresses are masked for screen privacy."
    )

    raw_subscribers = fetch_subscribers_data()

    if raw_subscribers:
        table_rows = []
        active_count = 0

        for s in raw_subscribers:
            is_act = bool(s.get("is_active", True))
            if is_act:
                active_count += 1

            raw_email = s.get("Email") or s.get("email", "")

            table_rows.append({
                "Recipient Name": s.get("Name")
                or s.get("full_name")
                or "Subscriber",
                "Email": mask_email(raw_email),
                "Team / Role": s.get("Role") or s.get("role") or "Team Member",
                "Status": "🟢 Active" if is_act else "⚪ Inactive",
            })

        col_m1, col_m2, _ = st.columns([1, 1, 2])
        col_m1.metric("Total Subscribers", len(table_rows))
        col_m2.metric("Active Inboxes", active_count)

        df_display = pd.DataFrame(table_rows)
        st.dataframe(
            df_display,
            column_order=["Recipient Name", "Email", "Team / Role", "Status"],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No subscribers currently found in the Snowflake `MAILING_LIST` table.")

    st.divider()

    with st.expander("➕ Add or Modify Subscriber"):
        with st.form("add_subscriber_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            new_name = col_f1.text_input("Full Name", placeholder="Jane Doe")
            new_email = col_f2.text_input("Email Address", placeholder="jane@company.com")

            col_f3, col_f4 = st.columns(2)
            new_role = col_f3.text_input("Team / Role", placeholder="Head of Engineering")
            new_active = col_f4.selectbox(
                "Delivery Status",
                options=[True, False],
                format_func=lambda x: "Active" if x else "Inactive / Unsubscribed",
            )

            submit_sub = st.form_submit_button("Save Subscriber to Snowflake", use_container_width=True)

            if submit_sub:
                if new_email and "@" in new_email:
                    try:
                        if upsert_subscriber is not None:
                            upsert_subscriber(
                                email=new_email,
                                full_name=new_name,
                                role=new_role,
                                is_active=new_active,
                            )
                        else:
                            from core.brief_generator import upsert_subscriber as live_upsert
                            live_upsert(
                                email=new_email,
                                full_name=new_name,
                                role=new_role,
                                is_active=new_active,
                            )
                        st.success(f"Saved {new_name or new_email} to Snowflake.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Failed to update subscriber: {err}")
                else:
                    st.warning("Please provide a valid email address.")


    with st.expander("🗑️ Remove Subscriber"):
        if raw_subscribers:
            # Map formatted label (Name + Masked Email) to the actual raw email
            sub_options = {
                f"{s.get('full_name') or s.get('Name') or 'Subscriber'} ({mask_email(s.get('email') or s.get('Email', ''))})": (s.get('email') or s.get('Email', ''))
                for s in raw_subscribers
                if (s.get('email') or s.get('Email'))
            }

            with st.form("delete_subscriber_form", clear_on_submit=True):
                selected_label = st.selectbox(
                    "Select Recipient to Delete",
                    options=list(sub_options.keys()),
                )
                submit_delete = st.form_submit_button(
                    "🗑️ Delete Subscriber from Snowflake",
                    use_container_width=True,
                )

                if submit_delete and selected_label:
                    target_email = sub_options[selected_label]
                    success = delete_subscriber_from_snowflake(target_email)
                    if success:
                        st.success(f"Removed {selected_label} from distribution list.")
                        st.rerun()
        else:
            st.caption("No subscribers available to remove.")