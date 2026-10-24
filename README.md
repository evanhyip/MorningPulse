# ☀️ MorningPulse

Autonomous executive telemetry and root-cause intelligence engine built for Cal Hacks 13.0.

---

## Overview

MorningPulse monitors business and infrastructure telemetry, detects statistical anomalies using a rolling baseline, cross-references anomalies with system logs, and uses Snowflake Cortex (`AI_COMPLETE`) to synthesize an executive brief with concrete incident remediation steps.

```
[seed_metrics.csv] ──► [detector.py: Rolling Z-Score]
                              │
                              ▼ (Flagged Outliers)
[logs.py: System Logs] ──► [brief_generator.py]
                              │
                              ▼ (Snowflake Statements REST API)
                    [Snowflake Cortex: AI_COMPLETE]
                              │
                              ▼ (Structured Executive Brief)
                     [Streamlit Dashboard (app.py)]
```

---

## Features

- **Statistical Anomaly Detection**: 14-day rolling mean ($\mu$) and standard deviation ($\sigma$) Z-score thresholding ($\vert{}z\vert{} \ge 2.5$) on the latest day's metrics.
- **Log Correlation**: Matches metric spikes against deployment events and HTTP error traces.
- **Snowflake Cortex Integration**: Direct REST API integration calling `AI_COMPLETE` with `llama3.1-8b` to pinpoint root causes and calculate financial impact.
- **Human-in-the-Loop UI**: Interactive Streamlit interface with 14-day trend charts and staged remediation actions (e.g., service rollback, status notifications).

---

## Tech Stack

- **Frontend**: Streamlit, Plotly
- **Data Processing**: Python 3.11+, Pandas
- **AI / LLM Engine**: Snowflake Cortex (`AI_COMPLETE` via SQL Statements REST API)
- **Model**: `llama3.1-8b`

---

## Project Structure

```text
morningpulse/
├── .streamlit/
│   └── secrets.toml          # Local secrets (ignored by Git)
├── app.py                    # Streamlit dashboard interface
├── brief_generator.py        # Snowflake Cortex REST API synthesis
├── detector.py               # Rolling Z-score anomaly detector
├── generate_data.py          # Synthetic 60-day telemetry generator
├── logs.py                   # Mock deployment and error logs
├── seed_metrics.csv          # Telemetry dataset
├── requirements.txt          # Python dependencies
├── .gitignore
└── README.md
```

---

## Getting Started

### 1. Prerequisites

- Python 3.10+
- A Snowflake account with Cortex AI functions enabled and a Personal Access Token (PAT).

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone [https://github.com/YOUR_USERNAME/morningpulse.git](https://github.com/YOUR_USERNAME/morningpulse.git)
cd morningpulse

python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory:

```env
SNOWFLAKE_ACCOUNT="your-org-your-account"
SNOWFLAKE_TOKEN="your_personal_access_token"
```

### 4. Run the Pipeline

Generate the telemetry data:

```bash
python generate_data.py
```

Run the statistical detector:

```bash
python detector.py
```

Launch the Streamlit executive application:

```bash
streamlit run app.py
```

The application runs locally at `http://localhost:8501`.