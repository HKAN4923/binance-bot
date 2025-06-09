# telegram_notifier.py
import os
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    """
    Send message to Telegram chat
    """
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_position_alert(symbol, side, quantity, entry_price, sl_price, tp_price):
    """
    Send position alert with detailed information
    """
    message = f"New position opened:\n" \
             f"Symbol: {symbol}\n" \
             f"Side: {side}\n" \
             f"Quantity: {quantity}\n" \
             f"Entry Price: {entry_price:.2f}\n" \
             f"Stop Loss: {sl_price:.2f}\n" \
             f"Take Profit: {tp_price:.2f}"
    return send_telegram_message(message)

def send_position_close(symbol, side, quantity):
    """
    Send position close alert
    """
    message = f"Position closed:\n" \
             f"Symbol: {symbol}\n" \
             f"Side: {side}\n" \
             f"Quantity: {quantity}"
    return send_telegram_message(message)

def send_status_update(symbol, position_size, entry_price, current_price, pnl):
    """
    Send hourly status update
    """
    message = f"Position Status:\n" \
             f"Symbol: {symbol}\n" \
             f"Position Size: {position_size}\n" \
             f"Entry Price: {entry_price:.2f}\n" \
             f"Current Price: {current_price:.2f}\n" \
             f"PnL: {pnl:.2f} USDT"
    return send_telegram_message(message)

def send_error_alert(error_message):
    """
    Send error alert
    """
    message = f"Error Alert:\n" \
             f"{error_message}"
    return send_telegram_message(message)