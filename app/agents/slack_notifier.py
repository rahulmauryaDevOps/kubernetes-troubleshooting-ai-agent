import os
import requests
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_alert(message):
    if not WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL missing in .env")

    response = requests.post(
        WEBHOOK_URL,
        json={"text": message},
        timeout=10
    )

    response.raise_for_status()
    return response.text == "ok"
