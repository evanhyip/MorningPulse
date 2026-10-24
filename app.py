"""
app.py
MorningPulse: Autonomous Executive Telemetry & Incident Intelligence Engine.
Streamlit dashboard with dynamic metric discovery, anomaly triage, and interactive AI Chief of Staff.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from core.detector import (
    fetch_telemetry_from_snowflake,
    detect_today_anomalies,
    get_snowflake_config,
)
from core.brief_generator import (
    generate_executive_brief,
    ask_chief_of_staff,
    get_cached_brief_for_today,
    save_brief_to_cache,
    fetch_mailing_list,
)

load_dotenv()

st.set_page_config(
    page_title="MorningPulse | Executive Cockpit",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Sidebar Configuration & Telemetry Ingestion
# ---------------------------------------------------------
cfg = get_snowflake_config()

with st.sidebar:
    st.title("⚡ MorningPulse")
    st.caption("Autonomous Incident & Executive Telemetry Engine")
    st.markdown("---")

    st.subheader("Target Warehouse")
    st.code(
        f"DB:    {cfg['database']}\n"
        f"SCHEMA:{cfg['schema']}\n"
        f"TABLE: {cfg['table']}\n"
        f"WH:    {cfg['warehouse']}",
        language="text",
    )

    lookback = st.slider("Lookback Window (Days)", min_value=7, max_value=60, value=14, step=7)
    z_thresh = st.slider("Z-Score Sensitivity", min_value=1.5, max_value=3.5, value=2.0, step=0.1)
    pct_thresh = st.slider("Min % Delta Threshold", min_value=10, max_value=50, value=15, step=5)

    if st.button("🔄 Refresh Telemetry"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------
# Data Loading
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def load_data(lookback_days: int) -> pd.DataFrame:
    return fetch_telemetry_from_snowflake(lookback_days=lookback_days)

with st.spinner("Querying Snowflake telemetry..."):
    try:
        df = load_data(lookback)
    except Exception as e:
        st.error(f"Failed to ingest telemetry from Snowflake: {e}")
        st.stop()

if df.empty:
    st.warning(f"No records found in table `{cfg['table']}`.")
    st.stop()

anomalies = detect_today_anomalies(df, z_threshold=z_thresh, min_pct_delta=pct_thresh)
risks = anomalies.get("risks", [])
opps = anomalies.get("opportunities", [])

# ---------------------------------------------------------
# Tab Layout
# ---------------------------------------------------------
tab_brief, tab_cockpit, tab_chat, tab_mailing = st.tabs([
    "📋 Executive Briefing",
    "📊 Metric Cockpit",
    "🤖 Chief of Staff Chat",
    "📬 Mailing List",
])

# ---------------------------------------------------------
# Tab 1: Executive Briefing
# ---------------------------------------------------------
with tab_brief:
    st.subheader("Daily Incident & Operational Briefing")

    # Check database cache first to avoid redundant LLM invocations
    cached_brief = get_cached_brief_for_today()

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        regen_brief = st.button("⚡ Generate New Brief")

    if regen_brief or not cached_brief:
        with st.spinner("Synthesizing brief via Snowflake Cortex AI..."):
            try:
                brief_content = generate_executive_brief(anomalies)
                save_brief_to_cache(brief_content)
                cached_brief = brief_content
            except Exception as e:
                st.error(f"Error generating brief: {e}")

    if cached_brief:
        st.markdown(cached_brief)
    else:
        st.info("No briefing available. Click above to generate one.")

    st.markdown("---")
    st.subheader("Detected Statistical Anomalies")

    col_r, col_o = st.columns(2)
    with col_r:
        st.error(f"🚨 Operational Risks ({len(risks)})")
        for r in risks:
            unit = r.get("unit", "")
            st.metric(
                label=f"[{r.get('department', 'Core')}] {r['metric_name']}",
                value=f"{r['current_value']} {unit}".strip(),
                delta=f"{r['percent_delta']} (Z: {r['z_score']})",
                delta_color="inverse",
            )

    with col_o:
        st.success(f"🚀 Growth Opportunities ({len(opps)})")
        for o in opps:
            unit = o.get("unit", "")
            st.metric(
                label=f"[{o.get('department', 'Core')}] {o['metric_name']}",
                value=f"{o['current_value']} {unit}".strip(),
                delta=f"{o['percent_delta']} (Z: {o['z_score']})",
                delta_color="normal",
            )

# ---------------------------------------------------------
# Tab 2: Metric Cockpit
# ---------------------------------------------------------
with tab_cockpit:
    st.subheader("Telemetry Time-Series Explorer")

    available_metrics = sorted(df["metric_name"].dropna().unique().tolist())
    selected_metric = st.selectbox("Select Metric", options=available_metrics)

    metric_df = df[df["metric_name"] == selected_metric].sort_values("metric_date")
    unit_str = metric_df["unit"].iloc[-1] if "unit" in metric_df.columns and not metric_df.empty else ""

    fig = px.line(
        metric_df,
        x="metric_date",
        y="metric_value",
        title=f"{selected_metric} ({unit_str})" if unit_str else selected_metric,
        markers=True,
        labels={"metric_date": "Date", "metric_value": f"Value ({unit_str})" if unit_str else "Value"},
    )
    fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View Raw Normalized Data"):
        st.dataframe(metric_df, use_container_width=True)

# ---------------------------------------------------------
# Tab 3: Interactive Chief of Staff
# ---------------------------------------------------------
with tab_chat:
    st.subheader("AI Chief of Staff Assistant")
    st.caption("Ask questions grounded directly in today's anomalies and telemetry.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt := st.chat_input("e.g. Which team should respond to the checkout spike?"):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consulting warehouse intelligence..."):
                try:
                    response_text = ask_chief_of_staff(
                        user_query=user_prompt,
                        context=cached_brief or str(anomalies),
                    )
                except Exception as e:
                    response_text = f"Error querying AI assistant: {e}"

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

# ---------------------------------------------------------
# Tab 4: Mailing List
# ---------------------------------------------------------
with tab_mailing:
    st.subheader("Executive Distribution Subscribers")
    try:
        subscribers = fetch_mailing_list()
        if subscribers:
            st.table(pd.DataFrame(subscribers))
        else:
            st.info("No active recipients found in MAILING_LIST table.")
    except Exception as e:
        st.error(f"Error loading subscribers: {e}")