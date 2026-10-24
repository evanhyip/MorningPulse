# ☀️ MorningPulse

**Autonomous Executive Telemetry & Incident Intelligence Engine**  
*Built for Cal Hacks 13.0*

---

## 📌 Executive Overview

**MorningPulse** transforms raw telemetry data stored in Snowflake into an actionable morning intelligence briefing for leadership. Instead of forcing executives to parse disparate metric dashboards and infrastructure logs, MorningPulse:

1. **Monitors Telemetry in Snowflake**: Queries historical business metrics directly from a Snowflake warehouse table via the Snowflake SQL Statements REST API.
2. **Detects Statistical Anomalies**: Computes rolling 14-day baseline statistical variances ($\vert{}Z\vert{} \ge 2.5$) using shifted trailing windows in Pandas.
3. **Pinpoints Root Causes via Snowflake Cortex**: Correlates metric spikes against deployment events and error logs using foundational LLMs (`llama3.1-8b`, `llama3.1-70b`, `mistral-large2`) hosted on Snowflake Cortex `AI_COMPLETE`.
4. **Enables Conversational Drill-Downs**: Features an interactive "AI Chief of Staff" agent to answer ad-hoc executive inquiries regarding financial exposure, blast radius, and system health.
5. **Stages Human-in-the-Loop Remediation**: Provides immediate one-click mitigation dispatch (e.g., automated service rollbacks, incident status page broadcasts).

---

## 🏗️ Architecture

```
                       ┌────────────────────────────────────────┐
                       │          Snowflake Warehouse           │
                       │   MORNINGPULSE_DB.TELEMETRY.METRICS    │
                       └───────────────────┬────────────────────┘
                                           │
                                           │ Snowflake SQL Statements REST API
                                           ▼
                       ┌────────────────────────────────────────┐
                       │          Statistical Detector          │
                       │       (14-Day Rolling Z-Scores)        │
                       └───────────────────┬────────────────────┘
                                           │
                                           │ Flagged Outliers + System Logs
                                           ▼
┌──────────────────────┐       ┌────────────────────────────────────────┐
│  Executive Dashboard │ ◄──── │       Snowflake Cortex Engine          │
│   (Streamlit App)    │       │     AI_COMPLETE (Llama 3.1 / Mistral)  │
└──────────┬───────────┘       └───────────────────┬────────────────────┘
           │                                       │
           │ Interactive Inquiries                 │ Contextual Answers
           └───────────────────► Chat Agent ◄──────┘
```

---

## ✨ Key Features

- **Warehouse-Native Architecture**: Operates directly against live Snowflake tables (`MORNINGPULSE_DB.TELEMETRY.BUSINESS_METRICS`) with cached REST queries to conserve compute credits.
- **Executive-First Vocabulary**: Replaces technical jargon (e.g., Z-scores, snake_case column names) with plain-language business titles (e.g., "Payment Checkout Failure Rate") and intuitive severity badges (🔴 *Critical Outlier*, 🟠 *Moderate Warning*).
- **Customizable AI Specs**: Dynamic sidebar controls in Streamlit allowing runtime selection of Cortex models (`llama3.1-8b`, `llama3.1-70b`, `llama3.1-405b`, `mistral-large2`, `snowflake-arctic`), max output tokens, and temperature sampling.
- **Gated Conversational Agent**: Stateful, multi-turn AI interrogation interface that unlocks once the morning brief is synthesized, grounding follow-up answers exclusively in verified warehouse metrics and logs.
- **Human-in-the-Loop Actions**: Staged incident resolution buttons ensuring production commands (like cluster rollbacks) require human authorization before execution.

---

## 📂 Repository Structure

```text
MorningPulse/
├── app.py                      # Streamlit frontend & executive interface
├── core/
│   ├── __init__.py
│   ├── brief_generator.py      # Snowflake Cortex synthesis & chat agent
│   ├── detector.py             # Snowflake REST query & rolling Z-score math
│   └── logs.py                 # Telemetry error and deployment log provider
├── data/
│   └── seed_metrics.csv        # Baseline telemetry dataset (300 records)
├── scripts/
│   └── generate_data.py        # Synthetic 60-day telemetry generation script
├── requirements.txt            # Python dependencies
├── .env.example                # Template for credentials
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- A Snowflake account with Cortex AI functions enabled and a Personal Access Token (PAT).

### 2. Environment Setup

Clone the repository and install required packages:

```bash
git clone [https://github.com/YOUR_USERNAME/MorningPulse.git](https://github.com/YOUR_USERNAME/MorningPulse.git)
cd MorningPulse

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
SNOWFLAKE_ACCOUNT="your-org-your-account"
SNOWFLAKE_TOKEN="your_snowflake_personal_access_token"
```

---

## 🗄️ Snowflake Database Initialization

Run the following SQL block in a Snowflake Worksheet to configure the database, schema, and telemetry table:

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS MORNINGPULSE_DB;
USE DATABASE MORNINGPULSE_DB;

CREATE SCHEMA IF NOT EXISTS TELEMETRY;
USE SCHEMA TELEMETRY;

CREATE OR REPLACE TABLE BUSINESS_METRICS (
    metric_date DATE,
    department VARCHAR(50),
    metric_name VARCHAR(100),
    metric_value FLOAT,
    unit VARCHAR(20)
);
```

### Loading Data
Load `data/seed_metrics.csv` into `BUSINESS_METRICS` via **Snowsight** (**Data** $\rightarrow$ **Databases** $\rightarrow$ **MORNINGPULSE_DB** $\rightarrow$ **TELEMETRY** $\rightarrow$ **BUSINESS_METRICS** $\rightarrow$ **Load Data**), selecting CSV format and setting **Skip first line** to 1.

Verify the table population:
```sql
SELECT COUNT(*) FROM MORNINGPULSE_DB.TELEMETRY.BUSINESS_METRICS;
-- Expected output: 300 rows
```

---

## 🖥️ Running the Application

Launch the Streamlit executive application:

```bash
streamlit run app.py
```

The application will be live at `http://localhost:8501`.

### Verification Walkthrough
1. **Inspect Incidents**: Review top-level anomaly cards showing live deviations against trailing 14-day baselines.
2. **Review Trajectory**: Inspect interactive Plotly line charts displaying historical trends for checkout failures and refund spikes.
3. **Generate Brief**: Click **Generate Morning Brief** to trigger Snowflake Cortex `AI_COMPLETE`, which correlates anomalies with deployment logs to produce root-cause analysis.
4. **Interrogate the Agent**: Scroll to the unlocked **Ask the AI Chief of Staff** panel and query specifics (e.g., *"What caused the SEPA gateway errors?"* or *"What is our financial exposure?"*).
5. **Stage Mitigation**: Use the staged remediation buttons to simulate operational rollbacks.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
| :--- | :--- | :--- |
| **Data Warehouse** | Snowflake | Relational store for telemetry (`MORNINGPULSE_DB`) |
| **Data API** | Snowflake SQL Statements API v2 | REST interface for warehouse queries |
| **AI / Synthesis** | Snowflake Cortex (`AI_COMPLETE`) | Managed LLM inference (`llama3.1-8b`, `llama3.1-70b`) |
| **Analytics** | Python, Pandas, NumPy | 14-day rolling window baseline and Z-score calculations |
| **User Interface** | Streamlit, Plotly | Interactive executive monitoring and conversational UI |