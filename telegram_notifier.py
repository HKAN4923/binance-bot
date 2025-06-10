from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(message: str) -> bool:
    """Send a message to the configured Telegram chat."""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def send_position_alert(symbol: str, side: str, quantity: float, entry_price: float, sl_price: float, tp_price: float) -> bool:
    message = (
        f"New position opened:\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Quantity: {quantity}\n"
        f"Entry Price: {entry_price:.2f}\n"
        f"Stop Loss: {sl_price:.2f}\n"
        f"Take Profit: {tp_price:.2f}"
    )
    return send_telegram_message(message)


def send_position_close(symbol: str, side: str, quantity: float) -> bool:
    message = (
        f"Position closed:\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Quantity: {quantity}"
    )
    return send_telegram_message(message)


def send_error_alert(error_message: str) -> bool:
    message = f"Error Alert:\n{error_message}"
    return send_telegram_message(message)
