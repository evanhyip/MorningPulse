# app.py
import pandas as pd
import plotly.express as px
import streamlit as st

from brief_generator import generate_executive_brief, query_cortex_chat
from detector import detect_today_anomalies, fetch_telemetry_from_snowflake

st.set_page_config(page_title="MorningPulse", page_icon="☀️", layout="wide")

# --- SIDEBAR: SNOWFLAKE CORTEX SPEC CONTROLS ---
with st.sidebar:
    st.header("⚙️ Snowflake Cortex Settings")
    selected_model = st.selectbox(
        "Model",
        options=["llama3.1-8b",
        "llama3.1-70b",
        "llama3.1-405b",
        "mistral-large2",
        "mixtral-8x7b",
        "snowflake-arctic"],
        index=0,
        help="LLM routed to Snowflake AI_COMPLETE",
    )
    max_tokens = st.slider(
        "Max Output Tokens",
        min_value=128,
        max_value=2048,
        value=512,
        step=64,
        help="Ceiling on tokens returned by AI_COMPLETE",
    )
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="Sampling temperature for deterministic/creative synthesis",
    )
    st.divider()
    st.caption("Database: `MORNINGPULSE_DB.TELEMETRY`")
    st.caption("Warehouse: `COMPUTE_WH`")


# --- DATA FETCHING & ANOMALY DETECTION ---
@st.cache_data(ttl=600)
def load_telemetry_data() -> pd.DataFrame:
    return fetch_telemetry_from_snowflake()


st.title("☀️ MorningPulse")
st.caption(
    "Live Warehouse Telemetry Detection & Autonomous Cortex AI Synthesis"
)

with st.spinner("Connecting to Snowflake warehouse..."):
    try:
        df = load_telemetry_data()
    except Exception as e:
        st.error(f"Failed to query Snowflake: {e}")
        st.stop()

anomalies = detect_today_anomalies(df)

# --- OVERNIGHT ANOMALY METRIC CARDS ---
st.markdown("### 🚨 Overnight Anomalies Detected")
if anomalies:
    cols = st.columns(min(len(anomalies), 4))
    for idx, a in enumerate(anomalies):
        with cols[idx % 4]:
            st.metric(
                label=f"{a['department']} · {a['metric_name']}",
                value=f"{a['current_value']} {a['unit']}",
                delta=f"{a['percent_delta']} (Z: {a['z_score']})",
                delta_color="inverse",
            )
else:
    st.success(
        "All operational metrics are within nominal 14-day rolling baselines (Z < 2.5)."
    )

# --- TELEMETRY TREND VISUALIZER ---
st.markdown("### 📈 Telemetry Trajectory")
available_metrics = df["metric_name"].unique().tolist()
default_idx = (
    available_metrics.index("checkout_failure_rate_pct")
    if "checkout_failure_rate_pct" in available_metrics
    else 0
)

selected_metric = st.selectbox(
    "Select metric to inspect:", available_metrics, index=default_idx
)
metric_df = (
    df[df["metric_name"] == selected_metric]
    .sort_values("metric_date")
    .tail(14)
)

fig = px.line(
    metric_df,
    x="metric_date",
    y="metric_value",
    markers=True,
    title=f"14-Day Trailing Trend: {selected_metric}",
    labels={"metric_date": "Date", "metric_value": "Metric Value"},
)
st.plotly_chart(fig, use_container_width=True)

# --- EXECUTIVE BRIEFING SECTION ---
st.divider()
st.subheader("📋 Executive Incident Briefing")

if st.button("Generate Morning Brief", type="primary"):
    with st.spinner(
        f"Snowflake Cortex ({selected_model}) is synthesizing telemetry..."
    ):
        try:
            brief = generate_executive_brief(
                anomalies=anomalies,
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            st.session_state["brief"] = brief
        except Exception as e:
            st.error(f"Error calling Snowflake Cortex: {e}")

if "brief" in st.session_state and st.session_state["brief"]:
    with st.container(border=True):
        st.markdown(st.session_state["brief"])

    st.markdown("#### ⚡ Staged Remediation Actions")
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("🚨 Trigger Rollback (`checkout-service-v2.14`)"):
            st.success(
                "Rollback command dispatched to cluster via Kubernetes API."
            )
    with col_act2:
        if st.button("📢 Broadcast Status Incident Advisory"):
            st.info("Incident advisory published to company status channels.")

# --- CONVERSATIONAL CORTEX AGENT (GATED BEHIND BRIEF GENERATION) ---
st.divider()
st.subheader("💬 Interrogate the Pulse (Live Snowflake Agent)")

if not st.session_state.get("brief"):
    st.info(
        "🔒 **Agent Locked:** Click **Generate Morning Brief** above to synthesize telemetry before starting an investigation."
    )
else:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display prior conversation history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat prompt handler
    if prompt := st.chat_input(
        "Ask about root causes, rollback steps, or impacts..."
    ):
        st.session_state["chat_history"].append(
            {"role": "user", "content": prompt}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"Consulting Snowflake Cortex ({selected_model})..."):
                try:
                    agent_response = query_cortex_chat(
                        conversation_history=st.session_state["chat_history"],
                        anomalies=anomalies,
                        system_brief=st.session_state["brief"],
                        model=selected_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    st.markdown(agent_response)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": agent_response}
                    )
                except Exception as e:
                    st.error(f"Error querying Snowflake Cortex Agent: {e}")