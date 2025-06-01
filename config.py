# config.py

import os
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# 1. 리미트 주문/지표 관련 파라미터 (가장 위에 모아두어 수정이 쉽도록 함)
# ─────────────────────────────────────────────────────────────────────────────

# (1) 진입 신호용 지표 임계치
PRIMARY_THRESHOLD   = int(os.getenv("PRIMARY_THRESHOLD", 3))    # 1분/5분 지표(5개) 중 최소 일치 개수
AUX_COUNT_THRESHOLD = int(os.getenv("AUX_COUNT_THRESHOLD", 2))  # 보조 지표(30m EMA, OBV, 거래량 스파이크, 볼린저) 중 최소 일치 개수

# (2) 30분 EMA 계산 기간
EMA_SHORT_LEN = int(os.getenv("EMA_SHORT_LEN", 20))  # 30m EMA 단기 기간 (예: 20)
EMA_LONG_LEN  = int(os.getenv("EMA_LONG_LEN", 50))   # 30m EMA 장기 기간 (예: 50)

# (3) 거래량 스파이크 감지 시 필요한 배수 (최근 20봉 평균 대비)
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", 2.0))

# (4) 리미트 주문 대기 시간 기본값 (초 단위)
LIMIT_ORDER_WAIT_BASE = int(os.getenv("LIMIT_ORDER_WAIT_BASE", 6))

# (5) 리미트 주문 진입 시 가격 오프셋
LIMIT_OFFSET = Decimal(os.getenv("LIMIT_OFFSET", "0.0015"))  # 현재가 대비 0.15% 유리한 가격

# (6) TP/SL 비율
TP_RATIO = Decimal(os.getenv("TP_RATIO", "0.0175"))  # 익절 목표 1.75%
SL_RATIO = Decimal(os.getenv("SL_RATIO", "0.008"))   # 손절 목표 0.8%

# (7) PnL 기반 감시 임계값
PIL_LOSS_THRESHOLD   = Decimal(os.getenv("PIL_LOSS_THRESHOLD", "0.005"))  # 손실 감시 –0.5%
PIL_PROFIT_THRESHOLD = Decimal(os.getenv("PIL_PROFIT_THRESHOLD", "0.005"))  # 익절 감시 +0.5%

# (8) 시장 분석 주기 (초 단위)
ANALYSIS_INTERVAL_SEC = int(os.getenv("ANALYSIS_INTERVAL_SEC", 10))  # 기본 10초마다 시장 분석

# ─────────────────────────────────────────────────────────────────────────────
# 2. 레버리지 및 동시 포지션 제한
# ─────────────────────────────────────────────────────────────────────────────

LEVERAGE      = int(os.getenv("LEVERAGE", 10))   # 기본 레버리지 10배
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))   # 최대 동시 보유 포지션 개수

# ─────────────────────────────────────────────────────────────────────────────
# 3. 청산/모니터링 관련 파라미터
# ─────────────────────────────────────────────────────────────────────────────

MAX_TRADE_DURATION    = int(os.getenv("MAX_TRADE_DURATION", 45 * 60))   # 최대 보유시간 45분(초)
EMERGENCY_PERIOD      = int(os.getenv("EMERGENCY_PERIOD", 10 * 60))     # 10분 동안 드로우다운 체크
EMERGENCY_DROP_PERCENT = Decimal(os.getenv("EMERGENCY_DROP_PERCENT", "0.10"))  # 10% 손실 시 긴급 멈춤

# 부분 익절 비율 (예: 0.5 → 보유 물량의 50% 익절)
PARTIAL_EXIT_RATIO = Decimal(os.getenv("PARTIAL_EXIT_RATIO", "0.5"))

# ─────────────────────────────────────────────────────────────────────────────
# 4. 요약 전송 설정 (Telegram)
# ─────────────────────────────────────────────────────────────────────────────

# 매일 KST 기준으로 거래 요약을 보낼 시각 (시, 분) 목록
SUMMARY_TIMES = [
    (6, 30),   # 06:30
    (12, 0),   # 12:00
    (18, 0),   # 18:00
    (21, 30),  # 21:30
]

# ─────────────────────────────────────────────────────────────────────────────
# 5. API 키 및 Telegram Token/Chat ID
# ─────────────────────────────────────────────────────────────────────────────

BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# 환경 변수 검증: 없으면 즉시 오류
if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise RuntimeError("BINANCE API 키 또는 시크릿이 설정되지 않았습니다.")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("텔레그램 토큰 또는 챗 ID가 설정되지 않았습니다.")
