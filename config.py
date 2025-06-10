import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ✅ 민감 정보는 .env에서 불러옴
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # ✅ 트레이딩 설정
    EXCHANGE = os.getenv("EXCHANGE", "binance")
    LEVERAGE = int(os.getenv("LEVERAGE", 5))
    SLTP_RATIO = float(os.getenv("SLTP_RATIO", 1.8))
    ATR_PERIOD = int(os.getenv("ATR_PERIOD", 20))
    ENTRY_MULTIPLIER = float(os.getenv("ENTRY_MULTIPLIER", 2.0))
    EXIT_MULTIPLIER = float(os.getenv("EXIT_MULTIPLIER", 1.8))
    BREAKOUT_TF = os.getenv("BREAKOUT_TF", "1h")

    # ✅ 리스크 관리
    USDT_RISK_PER_TRADE = float(os.getenv("USDT_RISK_PER_TRADE", 10))  # 각 트레이드당 리스크 USDT 금액
