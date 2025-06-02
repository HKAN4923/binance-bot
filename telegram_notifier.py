import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, data=data, timeout=10)
        if not resp.ok:
            logging.error(f"텔레그램 전송 실패: {resp.text}")
    except Exception as e:
        logging.error(f"텔레그램 오류: {e}")

def send_telegram_photo(photo_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
            resp = requests.post(url, files=files, data=data, timeout=15)
        if not resp.ok:
            logging.error(f"텔레그램 사진 전송 실패: {resp.text}")
    except Exception as e:
        logging.error(f"텔레그램 오류: {e}")
