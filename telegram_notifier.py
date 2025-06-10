from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def send_position_alert(symbol, side, quantity, entry_price, sl_price, tp_price):
    message = (
        f"New position opened:\n"
        f"Symbol: {symbol}\nSide: {side}\nQuantity: {quantity}\n"
        f"Entry Price: {entry_price:.2f}\nStop Loss: {sl_price:.2f}\n"
        f"Take Profit: {tp_price:.2f}"
    )
    return send_telegram_message(message)

def send_position_close(symbol, side, quantity):
    message = (
        f"Position closed:\nSymbol: {symbol}\nSide: {side}\nQuantity: {quantity}"
    )
    return send_telegram_message(message)

def send_error_alert(error_message):
    message = f"Error Alert:\n{error_message}"
    return send_telegram_message(message)
