# ☀️ MorningPulse

**Autonomous Executive Telemetry & Incident Intelligence Engine**

Powered by Snowflake SQL REST API v2 & Snowflake AI Functions (`AI_COMPLETE`).

---

## 📌 Overview

MorningPulse monitors enterprise operational health by continuously querying business metrics in Snowflake, automatically isolating statistical anomalies (using dynamic lookback baselines and Z-score thresholding), and synthesizing crisp, actionable executive morning briefs powered by LLMs hosted directly inside Snowflake Cortex.

### Key Capabilities

* **Table & Schema Agnostic Ingestion**: Fully dynamic database and table coordinates. Handles case sensitivity, quoted identifiers, and schemas with spaces or custom names (e.g., `BUSINESS_METRICS`).
* **Resilient Snowflake REST Serialization**: Automatically decodes Snowflake SQL API v2 integer epoch day representations (e.g., `'20690'`) and string-encoded numbers.
* **Native Cortex AI Functions**: Migrated to native `AI_COMPLETE` using high-performance foundation models (`llama3.1-70b`, `llama3.1-8b`, `snowflake-arctic`).
* **Zero-Friction Executive Cockpit**: Streamlit application featuring live metric time-series exploration, automated risk/opportunity categorizations, persistent briefing caches, automated email dispatches, and an interactive AI Chief of Staff copilot.

---

## 🏗️ Architecture

```text
                       ┌────────────────────────────────────────┐
                       │            Snowflake Data Warehouse    │
                       │  - BUSINESS_METRICS (Telemetry)        │
                       │  - DAILY_BRIEFS (Cache & History)      │
                       │  - MAILING_LIST (Distribution)         │
                       └───────────────────▲────────────────────┘
                                           │
                           REST API v2 / SQL Statements
                                           │
                       ┌───────────────────▼────────────────────┐
                       │            MorningPulse Core           │
                       ├────────────────────────────────────────┤
                       │ core/detector.py:                      │
                       │   - Dynamic identifier quoting         │
                       │   - Epoch date & metric normalizer     │
                       │   - Statistical baseline & Z-scores    │
                       │                                        │
                       │ core/brief_generator.py:               │
                       │   - Snowflake AI_COMPLETE synthesis    │
                       │   - Executive prompt conditioning      │
                       │   - Brief persistence & mailing lists  │
                       └───────────────────▲────────────────────┘
                                           │
                       ┌───────────────────▼────────────────────┐
                       │          Presentation Tier             │
                       ├────────────────────────────────────────┤
                       │ app.py (Streamlit Dashboard):          │
                       │   - Tab 1: Executive Morning Pulse     │
                       │   - Tab 2: Enterprise Telemetry Cockpit│
                       │   - Tab 3: Mailing List Directory      │
                       │   - Sidebar: AI Chief of Staff Chat    │
                       │                                        │
                       │ scripts/dispatch_morning_pulse.py      │
                       │   - Automated scheduled dispatch engine│
                       └────────────────────────────────────────┘
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the project root:

```ini
# Snowflake Connection Coordinates
SNOWFLAKE_ACCOUNT="your-account-identifier"
SNOWFLAKE_TOKEN="your-rest-api-bearer-or-oauth-token"
SNOWFLAKE_WAREHOUSE="COMPUTE_WH"

# Target Database & Schema
SNOWFLAKE_DATABASE="MORNINGPULSE_DB"
SNOWFLAKE_SCHEMA="TELEMETRY"
SNOWFLAKE_TABLE="BUSINESS_METRICS"

# Email Dispatch Configuration (Optional)
RESEND_API_KEY="your-resend-api-key"
BRIEFING_SENDER_EMAIL="your-resend-created-email"
BRIEFING_RECIPIENT_EMAILS="valid-recipient-emails"
```

---

## 🚀 Getting Started

### 1. Prerequisites & Installation

Ensure you have Python 3.10+ installed.

```bash
# Clone the repository
git clone [https://github.com/evanhyip/MorningPulse.git](https://github.com/evanhyip/MorningPulse.git)
cd MorningPulse

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Verify Snowflake Connection & Anomaly Engine

Run the detector test suite directly from your terminal:

```bash
python -c "from core.detector import fetch_telemetry_from_snowflake, detect_today_anomalies; df = fetch_telemetry_from_snowflake(); print('Data shape:', df.shape); print('Anomalies found:', detect_today_anomalies(df))"
```

### 3. Verify Executive Brief Generation via Cortex

Test briefing synthesis with `llama3.1-70b`:

```bash
python -c "from core.detector import fetch_telemetry_from_snowflake, detect_today_anomalies; from core.brief_generator import generate_executive_brief; df = fetch_telemetry_from_snowflake(); anomalies = detect_today_anomalies(df); print(generate_executive_brief(anomalies))"
```

### 4. Launch the Dashboard

```bash
streamlit run app.py
```

---

## 📂 Repository Structure

```text
MorningPulse/
├── core/
│   ├── detector.py          # Dynamic telemetry extraction, schema mapping & anomaly detection
│   └── brief_generator.py   # AI_COMPLETE briefing synthesis, caching, and mailing lists
├── scripts/
│   └── dispatch_morning_pulse.py # Script for scheduled morning email runs
├── app.py                   # Executive Streamlit Cockpit
├── requirements.txt         # Dependencies
├── .env.example             # Template environment variables
└── README.md                # Project documentation
```

---

## 📊 Data Contracts

MorningPulse dynamically adapts to arbitrary table schemas, mapping the following canonical aliases into its internal pipeline:

| Internal Column | Accepted Column Aliases | Type | Description |
| :--- | :--- | :--- | :--- |
| `metric_date` | `date`, `timestamp`, `created_at`, `day`, `dt` | `DATE` / `TIMESTAMP` / Epoch Day | Metric observation date |
| `metric_name` | `kpi`, `metric`, `name`, `measure`, `indicator` | `VARCHAR` | Unique identifier for metric |
| `metric_value` | `value`, `val`, `amount`, `score`, `cnt` | `FLOAT` / `NUMERIC` | Metric reading |
| `department` | `dept`, `team`, `category`, `service` | `VARCHAR` | Operational department owner |
| `unit` | `units`, `uom` | `VARCHAR` | Display unit (`%`, `$`, `ms`, etc.) |

---

## 🔒 Security & Best Practices

* **Bearer Token Handling**: All queries use short-lived bearer tokens or secure personal tokens transmitted over HTTPS to Snowflake's REST API.
* **SQL Sanitization**: All user and system prompts are sanitized against single-quote SQL escapes prior to executing `AI_COMPLETE`.
* **Masked Data**: Sensitive stakeholder emails are masked within the Streamlit UI to safeguard privacy in live executive settings.