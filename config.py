import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

LEVERAGE = int(os.getenv("LEVERAGE", 5))
SLTP_RATIO = float(os.getenv("SLTP_RATIO", 1.8))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))
MAX_EXPOSURE = float(os.getenv("MAX_EXPOSURE", 0.3))
