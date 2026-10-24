import pandas as pd
import plotly.express as px
import streamlit as st

from brief_generator import generate_executive_brief
from detector import detect_today_anomalies, fetch_telemetry_from_snowflake
from logs import get_recent_system_events

st.set_page_config(
    page_title="MorningPulse | Autonomous Executive Brief",
    page_icon="☀️",
    layout="wide",
)

# Custom header
st.title("☀️ MorningPulse")
st.caption(
    "Autonomous Enterprise Telemetry & Root-Cause Synthesis · Powered by Snowflake AI"
)

# In app.py
@st.cache_data(ttl=600)
def load_data():
    return fetch_telemetry_from_snowflake()


# 1. Top Section: Detected Metric Anomalies
df = load_data()
anomalies = detect_today_anomalies(df)

st.markdown("### 🚨 Overnight Anomalies Detected")
cols = st.columns(len(anomalies))

for idx, a in enumerate(anomalies):
    with cols[idx]:
        st.metric(
            label=f"{a['department']} · {a['metric_name']}",
            value=f"{a['current_value']} {a['unit']}",
            delta=f"{a['percent_delta']} (Z: {a['z_score']})",
            delta_color="inverse",
        )

st.divider()

# 2. Middle Section: Visualizing the Outlier
col_chart, col_events = st.columns([3, 2])

with col_chart:
    st.subheader("📈 Telemetry Trend (Past 14 Days)")
    df = pd.read_csv("seed_metrics.csv")
    df["metric_date"] = pd.to_datetime(df["metric_date"])

    # Filter to checkout failure rate for the visual demo
    chart_metric = "checkout_failure_rate_pct"
    metric_df = df[df["metric_name"] == chart_metric].tail(14)

    fig = px.line(
        metric_df,
        x="metric_date",
        y="metric_value",
        markers=True,
        title=f"Metric: {chart_metric}",
        labels={
            "metric_value": "Failure Rate (%)",
            "metric_date": "Date",
        },
    )
    # Highlight the anomaly in red
    fig.update_traces(
        line_color="#2563EB", marker=dict(size=8, color="#DC2626")
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col_events:
    st.subheader("🪵 Cross-Referenced Logs")
    events = get_recent_system_events()
    for ev in events:
        badge = "🔴" if ev["type"] == "error_trace" else "⚙️"
        with st.expander(f"{badge} {ev['timestamp']} - {ev['service']}"):
            st.write(f"**Type:** `{ev['type']}`")
            st.write(f"**Message:** {ev['message']}")

st.divider()

# 3. Bottom Section: Autonomous Executive Briefing
st.subheader("📋 Executive Briefing & Incident Remediation")

if "brief" not in st.session_state:
    st.session_state["brief"] = None

col_btn, col_status = st.columns([1, 4])
with col_btn:
    if st.button("Generate Morning Brief", type="primary"):
        with st.spinner("Snowflake AI_COMPLETE is synthesizing telemetry..."):
            st.session_state["brief"] = generate_executive_brief()

if st.session_state["brief"]:
    # Render inside a clean bordered card
    with st.container(border=True):
        st.markdown(st.session_state["brief"])

    st.markdown("---")
    st.subheader("⚡ Autonomous Action Execution")

    act_col1, act_col2 = st.columns(2)
    with act_col1:
        if st.button(
            "🚀 Execute Staged Rollback: checkout-service-v2.13.9",
            use_container_width=True,
        ):
            st.success(
                "Rollback PR #1042 triggered and merged via deployment pipeline."
            )
    with act_col2:
        if st.button(
            "📢 Broadcast Status Incident Advisory to Customer Ops",
            use_container_width=True,
        ):
            st.info(
                "Advisory dispatched to #incident-payments and public status page updated."
            )

