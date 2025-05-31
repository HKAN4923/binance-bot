# config.py

import os
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# 레버리지 및 포지션 최대 개수
#   - LEVERAGE: 각 포지션에 적용할 레버리지 배수 (기본 10배)
#   - MAX_POSITIONS: 동시에 보유 가능한 최대 포지션 개수 (기본 3개)
LEVERAGE = int(os.getenv("LEVERAGE", 10))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))

# ─────────────────────────────────────────────────────────────────────────────
# 고정 익절/손절 비율
#   - FIXED_PROFIT_TARGET: 익절 목표 비율 (예: 0.025 → 2.5%)
#   - FIXED_LOSS_CAP_BASE: 최대 손절 비율 (익절 목표 / 1.75로 계산)
FIXED_PROFIT_TARGET = Decimal(os.getenv("FIXED_PROFIT_TARGET", "0.025"))
FIXED_LOSS_CAP_BASE = FIXED_PROFIT_TARGET / Decimal("1.75")

# ─────────────────────────────────────────────────────────────────────────────
# 최소 손절 폭
#   - MIN_SL: 최소 손절 비율 (예: 0.005 → 0.5%)
MIN_SL = Decimal(os.getenv("MIN_SL", "0.005"))

# ─────────────────────────────────────────────────────────────────────────────
# 부분 익절 관련 비율
#   - PARTIAL_EXIT_RATIO: 부분 익절 시 청산 비율 (예: 0.4 → 40% 물량 청산)
#   - PARTIAL_TARGET_RATIO: 부분 익절 목표 비율 (예: 0.6 → 60% 물량 청산 후 TP 비율)
PARTIAL_EXIT_RATIO = Decimal(os.getenv("PARTIAL_EXIT_RATIO", "0.4"))
PARTIAL_TARGET_RATIO = Decimal(os.getenv("PARTIAL_TARGET_RATIO", "0.6"))

# ─────────────────────────────────────────────────────────────────────────────
# 분석/포지션 관련 시간 설정 (초 단위)
#   - RECHECK_START: 진입 후 재판단을 시작할 대기 시간 (기본 20분)
#   - RECHECK_INTERVAL: 재판단 주기 (기본 5분)
#   - MAX_TRADE_DURATION: 최대 보유 시간 (기본 45분)
RECHECK_START = int(os.getenv("RECHECK_START", 20 * 60))
RECHECK_INTERVAL = int(os.getenv("RECHECK_INTERVAL", 5 * 60))
MAX_TRADE_DURATION = int(os.getenv("MAX_TRADE_DURATION", 45 * 60))

# ─────────────────────────────────────────────────────────────────────────────
# 분석 주기
#   - ANALYSIS_INTERVAL_SEC: 시장 분석(진입 조건 체크)을 수행할 간격 (기본 2.5초)
ANALYSIS_INTERVAL_SEC = int(os.getenv("ANALYSIS_INTERVAL_SEC", 2.5))

# ─────────────────────────────────────────────────────────────────────────────
# 긴급 정지(딥 드로우다운) 조건
#   - EMERGENCY_PERIOD: 손실을 체크할 기간 (기본 10분)
#   - EMERGENCY_DROP_PERCENT: 해당 기간 내 손실 기준치 (예: 0.10 → 10% 손실 시 긴급 정지)
EMERGENCY_PERIOD = int(os.getenv("EMERGENCY_PERIOD", 10 * 60))
EMERGENCY_DROP_PERCENT = Decimal(os.getenv("EMERGENCY_DROP_PERCENT", "0.10"))

# ─────────────────────────────────────────────────────────────────────────────
# 요약 전송 시간대 (KST 기준)
#   - SUMMARY_TIMES: 매일 거래 요약을 텔레그램으로 보낼 시각 (시, 분) 리스트
SUMMARY_TIMES = [
    (6, 30),   # 06:30 KST
    (12, 0),   # 12:00 KST
    (18, 0),   # 18:00 KST
    (21, 30),  # 21:30 KST
]

# ─────────────────────────────────────────────────────────────────────────────
# API 키 및 텔레그램 설정
#   - BINANCE_API_KEY / BINANCE_API_SECRET: Binance 선물 거래용 API 키
#   - TELEGRAM_TOKEN / TELEGRAM_CHAT_ID: 텔레그램 봇 알림용 설정
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 필수 환경 변수 체크
if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise RuntimeError("BINANCE API 키 또는 시크릿이 설정되지 않았습니다.")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("텔레그램 토큰 또는 챗 ID가 설정되지 않았습니다.")
