import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

    LEVERAGE = int(os.getenv("LEVERAGE", 10))
    SLTP_RATIO = float(os.getenv("SLTP_RATIO", 1.8))
    MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))
    MAX_EXPOSURE = float(os.getenv("MAX_EXPOSURE", 0.3))

    POSITION_SIZE = MAX_EXPOSURE
    POSITION_CHECK_INTERVAL = int(os.getenv("POSITION_CHECK_INTERVAL", 5))  # in seconds

    ATR_PERIOD = int(os.getenv("ATR_PERIOD", 20))
    ENTRY_MULTIPLIER = float(os.getenv("ENTRY_MULTIPLIER", 2.0))
    BREAKOUT_TF = os.getenv("BREAKOUT_TF", "1h")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")
