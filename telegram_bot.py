# telegram_bot.py

import os
import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Telegram Bot API 기본 URL
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_message(text: str):
    """
    텔레그램으로 텍스트 메시지 전송
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        if not resp.ok:
            logging.error(f"[텔레그램 전송 실패] status={resp.status_code}, resp={resp.text}")
    except Exception as e:
        logging.error(f"[텔레그램 메시지 예외] {e}")

def send_photo(photo_path: str, caption: str = ""):
    """
    텔레그램으로 사진 전송 (그래프 등)
    """
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=10
            )
        if not resp.ok:
            logging.error(f"[텔레그램 사진 전송 실패] status={resp.status_code}, resp={resp.text}")
    except Exception as e:
        logging.error(f"[텔레그램 사진 예외] {e}")
