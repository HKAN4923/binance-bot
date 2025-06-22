"""텔레그램 전송 모듈"""

import logging
import os
import requests

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

API_URL = f"https://api.telegram.org/bot{TOKEN}"


def send_message(text: str) -> None:
    """텔레그램 텍스트 메시지 전송"""
    if not TOKEN or not CHAT_ID:
        logging.warning("[텔레그램] 설정 정보 없음 - 메시지 전송 생략")
        return

    try:
        url = f"{API_URL}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logging.info("[텔레그램] 메시지 전송 성공")
    except Exception as e:
        logging.error(f"[텔레그램] 메시지 전송 실패: {e}")


def send_photo(photo_path: str, caption: str = "") -> None:
    """텔레그램 이미지 전송"""
    if not TOKEN or not CHAT_ID:
        logging.warning("[텔레그램] 설정 정보 없음 - 이미지 전송 생략")
        return

    try:
        url = f"{API_URL}/sendPhoto"
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": CHAT_ID, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=10)
            response.raise_for_status()
            logging.info("[텔레그램] 이미지 전송 성공")
    except Exception as e:
        logging.error(f"[텔레그램] 이미지 전송 실패: {e}")
