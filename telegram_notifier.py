import os
import requests
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, data=data)
        if not resp.ok:
            print("텔레그램 전송 실패:", resp.text)
    except Exception as e:
        print("텔레그램 오류:", e)
