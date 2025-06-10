er.# File: notifier.py
import requests
from config import Config

class TelegramNotifier:
    BASE_URL = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}"

    @classmethod
    def notify(cls, message: str):
        url = f"{cls.BASE_URL}/sendMessage"
        payload = {"chat_id": Config.TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload)
