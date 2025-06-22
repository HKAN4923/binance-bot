# config.py
import os
from dotenv import load_dotenv
from binance_client import get_top_volume_symbols

# .env 로드
load_dotenv()

# Binance API / Telegram 설정 (필수)
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise RuntimeError("BINANCE API 키 또는 시크릿이 설정되지 않았습니다.")
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("텔레그램 토큰 또는 챗 ID가 설정되지 않았습니다.")

# 봇 전반 동작 파라미터
MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", 5))
ANALYSIS_INTERVAL_SEC: int = int(os.getenv("ANALYSIS_INTERVAL_SEC", 60))
POSITION_CHECK_INTERVAL_SEC: int = int(os.getenv("POSITION_CHECK_INTERVAL_SEC", 30))
SUMMARY_INTERVAL_SEC: int = 2 * 60 * 60  # 2시간마다 요약 전송

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# 심볼 리스트: 24h 거래량 상위 N개 (기본 50개)
SYMBOL_LIMIT: int = int(os.getenv("SYMBOL_LIMIT", 50))
SYMBOLS: list = get_top_volume_symbols(limit=SYMBOL_LIMIT)

# 기타 상수
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
