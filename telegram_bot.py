"""Utility functions for sending messages to Telegram."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Optional


TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_URL = "https://api.telegram.org/bot{token}/{method}"


def _post(method: str, data: dict) -> None:
    """Internal helper to send POST requests to Telegram."""
    if not TOKEN or not CHAT_ID:
        logging.info("Telegram credentials not set. Skipping send.")
        return

    url = API_URL.format(token=TOKEN, method=method)
    encoded = urllib.parse.urlencode(data).encode()
    try:
        with urllib.request.urlopen(url, data=encoded, timeout=10) as resp:
            resp.read()
    except Exception as exc:  # pragma: no cover - network errors not fatal
        logging.error("Telegram send failed: %s", exc)


def send_message(text: str) -> None:
    """Send a text message to the configured chat."""
    _post("sendMessage", {"chat_id": CHAT_ID, "text": text})


def send_photo(photo_path: str, caption: Optional[str] = None) -> None:
    """Send a photo from a file path with optional caption."""
    if not TOKEN or not CHAT_ID:
        logging.info("Telegram credentials not set. Skipping photo send.")
        return

    url = API_URL.format(token=TOKEN, method="sendPhoto")
    with open(photo_path, "rb") as f:
        data = {
            "chat_id": CHAT_ID,
            "caption": caption or "",
        }
        form_data = urllib.parse.urlencode(data).encode()
        try:
            request = urllib.request.Request(url, data=form_data)
            with urllib.request.urlopen(request, timeout=10) as resp:
                resp.read()
        except Exception as exc:  # pragma: no cover
            logging.error("Telegram photo send failed: %s", exc)