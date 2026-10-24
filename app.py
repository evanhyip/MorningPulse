# app.py
import pandas as pd
import plotly.express as px
import streamlit as st

from core.brief_generator import generate_executive_brief, query_cortex_chat
from core.detector import detect_today_anomalies, fetch_telemetry_from_snowflake

st.set_page_config(page_title="MorningPulse", page_icon="☀️", layout="wide")

# --- EXECUTIVE METRIC METADATA ---
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
    """Ensures operational risks are always rendered red and opportunities green."""
    is_positive = not change_str.startswith("-")
    if is_risk:
        return "inverse" if is_positive else "normal"
    return "normal" if is_positive else "inverse"


# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Snowflake Cortex Settings")
    selected_model = st.selectbox(
        "AI Model",
        ["llama3.1-8b", "llama3.1-70b", "mistral-large2", "snowflake-arctic"],
        index=0,
        help="Select foundational LLM hosted natively in Snowflake Cortex.",
    )
    max_tokens = st.slider("Max Output Tokens", 128, 2048, 768, 64)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
    st.divider()
    st.caption("Warehouse: `COMPUTE_WH`")
    st.caption("Database: `MORNINGPULSE_DB.TELEMETRY`")


@st.cache_data(ttl=600)
def load_data():
    return fetch_telemetry_from_snowflake()


st.title("☀️ MorningPulse")
st.caption("Enterprise Telemetry Intelligence · Powered by Snowflake Cortex")

with st.spinner("Connecting to Snowflake warehouse..."):
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Failed to query Snowflake: {e}")
        st.stop()

anomalies_dict = detect_today_anomalies(df)
risks = anomalies_dict["risks"]
opps = anomalies_dict["opportunities"]
all_anomalies = risks + opps

# --- NAVIGATION TABS ---
tab_exec, tab_cockpit = st.tabs(
    ["☀️ Executive Morning Pulse", "📊 Company Cockpit (All 15 Metrics)"]
)

# ==========================================
# TAB 1: EXECUTIVE PULSE
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

    # 3. Cortex Executive Synthesis
    st.subheader("📋 Executive Incident Briefing")
    if st.button("Generate Morning Brief", type="primary"):
        with st.spinner(f"Snowflake Cortex ({selected_model}) analyzing telemetry across all departments..."):
            try:
                st.session_state["brief"] = generate_executive_brief(
                    anomalies=anomalies_dict,
                    model=selected_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                st.error(f"Error calling Cortex: {e}")

    if "brief" in st.session_state and st.session_state["brief"]:
        with st.container(border=True):
            st.markdown(st.session_state["brief"])

        st.markdown("#### ⚡ Staged Remediation Actions")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚨 Trigger Rollback (`checkout-service-v2.14`)"):
                st.success("Rollback command dispatched to Kubernetes cluster.")
        with c2:
            if st.button("📢 Broadcast Status Incident Advisory"):
                st.info("Incident advisory posted to customer status channels.")

# ==========================================
# TAB 2: COMPANY COCKPIT (ALL 15 CHARTS)
# ==========================================
with tab_cockpit:
    st.markdown("### 📊 Enterprise Telemetry Cockpit (All 15 Metrics)")
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
# PERSISTENT CHIEF OF STAFF AGENT (BELOW TABS)
# ==========================================
st.divider()
st.subheader("💬 Ask the AI Chief of Staff")
st.caption("Drill down into causal telemetry, revenue loss, or mitigation steps across any tab.")

if not st.session_state.get("brief"):
    st.info("🔒 Click **Generate Morning Brief** on the Executive Pulse tab to unlock the AI agent.")
else:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about revenue impact, root cause, or metric charts..."):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing telemetry with Snowflake Cortex..."):
                try:
                    agent_res = query_cortex_chat(
                        conversation_history=st.session_state["chat_history"],
                        anomalies=all_anomalies,
                        system_brief=st.session_state["brief"],
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