import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    EXCHANGE = os.getenv("EXCHANGE", "binance")
    LEVERAGE = int(os.getenv("LEVERAGE", 5))
    SLTP_RATIO = float(os.getenv("SLTP_RATIO", 1.8))
    SYMBOL_SOURCE = os.getenv("SYMBOL_SOURCE", "top_volume_100")
    MAX_POSITIONS = int(os.getenv("RISK_MAX_POSITIONS", 3))
    MAX_EXPOSURE = float(os.getenv("RISK_MAX_EXPOSURE", 0.30))
    ENTRY_TARGET_PER_DAY = int(os.getenv("ENTRY_TARGET_PER_DAY", 20))
    WIN_RATE_TARGET = float(os.getenv("WIN_RATE_TARGET", 0.55))
    ATR_PERIOD = int(os.getenv("ATR_PERIOD", 20))
    ENTRY_MULTIPLIER = float(os.getenv("ENTRY_MULTIPLIER", 2.0))
    EXIT_MULTIPLIER = float(os.getenv("EXIT_MULTIPLIER", 1.8))
    BREAKOUT_TF = os.getenv("BREAKOUT_TF", "1h")
    PULLBACK_TF = os.getenv("PULLBACK_TF", "15m")
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL_S", 10))  # seconds
    EMERGENCY_DRAWDOWN = float(os.getenv("EMERGENCY_DRAWDOWN", 0.05))  # 5%
