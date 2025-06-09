# telegram_notifier.py
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ✅ 텔레그램 메시지 전송 함수
def send_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[Telegram Error]: {e}")