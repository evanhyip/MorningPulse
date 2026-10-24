import os
from dotenv import load_dotenv
import requests

load_dotenv()

account = os.getenv("SNOWFLAKE_ACCOUNT")
token = os.getenv("SNOWFLAKE_TOKEN")

url = f"https://{account}.snowflakecomputing.com/api/v2/statements"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Escape single quotes in the prompt text
prompt = "Analyze overnight metrics and respond: Connection verified!"
sanitized_prompt = prompt.replace("'", "''")

payload = {
    "statement": f"SELECT AI_COMPLETE('llama3.1-8b', '{sanitized_prompt}') AS response;",
    "warehouse": "COMPUTE_WH",
}

response = requests.post(url, headers=headers, json=payload, timeout=30)

if response.status_code == 200:
    data = response.json()
    result_text = data["data"][0][0]
    print(f"Snowflake AI Output:\n{result_text}")
else:
    print(f"Error {response.status_code}: {response.text}")