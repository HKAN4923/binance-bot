import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API & Telegram
    BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

    # 레버리지 및 포지션
    LEVERAGE           = int(os.getenv("LEVERAGE", 5))
    MAX_POSITIONS      = int(os.getenv("MAX_POSITIONS", 3))
    MAX_EXPOSURE       = float(os.getenv("MAX_EXPOSURE", 0.30))  # 잔고 대비 진입 비중

    # 시장 분석 주기
    ANALYSIS_INTERVAL_SEC = int(os.getenv("ANALYSIS_INTERVAL_SEC", 10))

    # TP/SL 비율
    TP_RATIO           = float(os.getenv("TP_RATIO", 1.8))
    SL_RATIO           = float(os.getenv("SL_RATIO", 1.0))

    # 내 로직 지표 임계치
    PRIMARY_THRESHOLD    = int(os.getenv("PRIMARY_THRESHOLD", 3))
    AUX_COUNT_THRESHOLD  = int(os.getenv("AUX_COUNT_THRESHOLD", 2))

    # 라쉬케(ATR) 전략 설정
    ATR_PERIOD         = int(os.getenv("ATR_PERIOD", 20))
    ENTRY_MULTIPLIER   = float(os.getenv("ENTRY_MULTIPLIER", 2.0))
    BREAKOUT_TF        = os.getenv("BREAKOUT_TF", "1h")

    # 라쉬케 부가 전략 설정
    EMA_SHORT_LEN      = int(os.getenv("EMA_SHORT_LEN", 20))
    EMA_LONG_LEN       = int(os.getenv("EMA_LONG_LEN", 50))
    VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", 2.0))

    # 시간대
    TIMEZONE           = os.getenv("TIMEZONE", "Asia/Seoul")
