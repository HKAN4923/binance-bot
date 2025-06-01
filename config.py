# config.py

import os
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

# ======== TUNABLE STRATEGY PARAMETERS (초기 설정 시 수정 가능) ========
# 1분/5분 지표 일치 최소 개수 (기본 3개 → SETTINGS 조정)
PRIMARY_THRESHOLD = int(os.getenv("PRIMARY_THRESHOLD", 3))  # 5개 지표 중 최소 일치 개수
AUX_COUNT_THRESHOLD = int(os.getenv("AUX_COUNT_THRESHOLD", 2))  # 보조지표 최소 일치 개수

# 보조지표 계산용 EMA 기간
EMA_SHORT_LEN = int(os.getenv("EMA_SHORT_LEN", 20))  # 30m EMA 단기
EMA_LONG_LEN = int(os.getenv("EMA_LONG_LEN", 50))   # 30m EMA 장기

# 거래량 스파이크 멀티플
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", 2))

# 고정 TP/SL 비율 (TP: 1.75% / SL: 0.8%)
TP_RATIO = Decimal(os.getenv("TP_RATIO", "0.0175"))
SL_RATIO = Decimal(os.getenv("SL_RATIO", "0.008"))

# PnL 기준 (손실/익절 구간)
PIL_LOSS_THRESHOLD = Decimal(os.getenv("PIL_LOSS_THRESHOLD", "0.005"))   # –0.5%
PIL_PROFIT_THRESHOLD = Decimal(os.getenv("PIL_PROFIT_THRESHOLD", "0.005")) # +0.5%

# 리미트 주문 대기 시간 기본값 (초)
LIMIT_ORDER_WAIT_BASE = int(os.getenv("LIMIT_ORDER_WAIT_BASE", 6))

# 리미트 주문 가격 편차 (0.2% favorable)
LIMIT_OFFSET = Decimal(os.getenv("LIMIT_OFFSET", "0.0015"))

# 레버리지 및 동시 포지션 제한
LEVERAGE = int(os.getenv("LEVERAGE", 10))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))

# ======== 청산 및 모니터링 ========
# 최대 보유 시간 (초)
MAX_TRADE_DURATION = int(os.getenv("MAX_TRADE_DURATION", 45 * 60))

# 긴급 정지(딥 드로우다운) 조건
EMERGENCY_PERIOD = int(os.getenv("EMERGENCY_PERIOD", 10 * 60))
EMERGENCY_DROP_PERCENT = Decimal(os.getenv("EMERGENCY_DROP_PERCENT", "0.10"))

# 부분 익절 비율 (예: 0.5 → 50% 물량 청산)
PARTIAL_EXIT_RATIO = Decimal(os.getenv("PARTIAL_EXIT_RATIO", "0.5"))

# ======== 요약 전송 설정 ========
# 요약 전송 시각 (KST)
SUMMARY_TIMES = [
    (6, 30),   # 06:30
    (12, 0),   # 12:00
    (18, 0),   # 18:00
    (21, 30),  # 21:30
]

# ======== API 및 토큰 ========
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 필수 환경 변수 확인
if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise RuntimeError("BINANCE API 키 또는 시크릿이 설정되지 않았습니다.")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("텔레그램 토큰 또는 챗 ID가 설정되지 않았습니다.")
