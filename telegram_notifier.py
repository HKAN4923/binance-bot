import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except:
        pass

def send_position_alert(symbol, side, qty, entry, sl, tp):
    send_telegram(
        f"<b>▶ ENTRY</b>\n"
        f"{symbol} {side}\n"
        f"Qty: {qty}\n"
        f"Entry: {entry:.4f}\nSL: {sl:.4f} TP: {tp:.4f}"
    )

def send_position_close(symbol, side, qty):
    send_telegram(f"<b>▶ CLOSE</b>\n{symbol} {side}\nQty: {qty}")

def send_error_alert(msg: str):
    send_telegram(f"<b>⚠️ ERROR</b>\n{msg}")
