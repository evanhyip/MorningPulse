# scripts/dispatch_morning_pulse.py
import os
import markdown
import resend
from dotenv import load_dotenv

from core.detector import detect_today_anomalies
from core.brief_generator import generate_executive_brief, save_brief_to_snowflake

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")
SENDER = os.getenv("BRIEFING_SENDER_EMAIL", "onboarding@resend.dev")
RECIPIENTS = [
    email.strip()
    for email in os.getenv("BRIEFING_RECIPIENT_EMAILS", "").split(",")
    if email.strip()
]


def format_brief_to_html(raw_markdown: str) -> str:
    """Converts the raw Markdown briefing into a styled enterprise email template."""
    body_html = markdown.markdown(raw_markdown)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f9fafb;
          color: #111827;
          margin: 0;
          padding: 24px;
        }}
        .card {{
          max-width: 680px;
          margin: 0 auto;
          background: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 32px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .header {{
          border-bottom: 2px solid #f3f4f6;
          padding-bottom: 16px;
          margin-bottom: 24px;
        }}
        h1 {{
          font-size: 22px;
          color: #111827;
          margin: 0 0 6px 0;
        }}
        .subtitle {{
          font-size: 13px;
          color: #6b7280;
          margin: 0;
        }}
        h3 {{
          font-size: 16px;
          color: #1f2937;
          margin-top: 24px;
          border-bottom: 1px solid #f3f4f6;
          padding-bottom: 4px;
        }}
        p, li {{
          font-size: 14px;
          line-height: 1.6;
          color: #374151;
        }}
        code {{
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: #b91c1c;
        }}
        .footer {{
          margin-top: 32px;
          padding-top: 16px;
          border-top: 1px solid #f3f4f6;
          font-size: 12px;
          color: #9ca3af;
          text-align: center;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>☀️ MorningPulse · Executive Briefing</h1>
          <p class="subtitle">Autonomous Telemetry Intelligence · Powered by Snowflake Cortex</p>
        </div>
        <div class="content">
          {body_html}
        </div>
        <div class="footer">
          Delivered autonomously at 9:00 AM UTC. Reply to query the Chief of Staff agent.
        </div>
      </div>
    </body>
    </html>
    """


def send_daily_pulse_email(brief_text: str | None = None) -> dict:
    """Executes the full generation, persistence, and dispatch pipeline."""
    if not resend.api_key:
        raise ValueError("RESEND_API_KEY is not defined in your environment.")
    if not RECIPIENTS:
        raise ValueError("BRIEFING_RECIPIENT_EMAILS is not defined in your environment.")

    # Generate if not provided
    if not brief_text:
        print("1/3 Detecting telemetry anomalies...")
        anomalies = detect_today_anomalies()
        print("2/3 Generating Cortex executive brief...")
        brief_text = generate_executive_brief(anomalies=anomalies)

    # Save to Snowflake persistence table
    print("3/3 Committing brief to Snowflake DAILY_BRIEFS...")
    save_brief_to_snowflake(brief_text=brief_text, sent_via_email=True)

    # Render HTML and send via Resend
    html_content = format_brief_to_html(brief_text)
    response = resend.Emails.send({
        "from": f"MorningPulse <{SENDER}>",
        "to": RECIPIENTS,
        "subject": "☀️ MorningPulse: Daily Executive Incident & Telemetry Briefing",
        "html": html_content,
    })

    print(f"✅ Dispatched daily email to {RECIPIENTS}. Resend ID: {response.get('id')}")
    return response


if __name__ == "__main__":
    send_daily_pulse_email()