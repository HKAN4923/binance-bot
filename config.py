import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# 1. 리미트 주문/지표 관련 파라미터
PRIMARY_THRESHOLD = int(os.getenv("PRIMARY_THRESHOLD", 4))       # 3 → 4 (더 엄격)
AUX_COUNT_THRESHOLD = int(os.getenv("AUX_COUNT_THRESHOLD", 3))   # 2 → 3

# 2. 30분 EMA 계산 기간 (변경 없음)
EMA_SHORT_LEN = int(os.getenv("EMA_SHORT_LEN", 20))
EMA_LONG_LEN = int(os.getenv("EMA_LONG_LEN", 50))

# 3. 거래량 스파이크 감지 (변경 없음)
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", 2.0))

# 4. 리미트 주문 대기 시간 (변경 없음)
LIMIT_ORDER_WAIT_BASE = int(os.getenv("LIMIT_ORDER_WAIT_BASE", 7))

# 5. 리미트 주문 진입 시 가격 오프셋 (변경 없음)
LIMIT_OFFSET = Decimal(os.getenv("LIMIT_OFFSET", "0.0002"))

# 6. TP/SL 비율 - 핵심 개선!
TP_RATIO = Decimal(os.getenv("TP_RATIO", "0.025"))  # 1.75% → 2.5%
SL_RATIO = Decimal(os.getenv("SL_RATIO", "0.005"))  # 0.8% → 0.5%

# 7. PnL 기반 감시 임계값 (변경 없음)
PIL_LOSS_THRESHOLD = Decimal(os.getenv("PIL_LOSS_THRESHOLD", "0.005"))
PIL_PROFIT_THRESHOLD = Decimal(os.getenv("PIL_PROFIT_THRESHOLD", "0.005"))

# 8. 시장 분석 주기 (변경 없음)
ANALYSIS_INTERVAL_SEC = int(os.getenv("ANALYSIS_INTERVAL_SEC", 10))

# 2. 레버리지 및 동시 포지션 제한
LEVERAGE = int(os.getenv("LEVERAGE", 10))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 3))

# 3. 청산/모니터링 관련 파라미터
MAX_TRADE_DURATION = int(os.getenv("MAX_TRADE_DURATION", 45 * 60))
EMERGENCY_PERIOD = int(os.getenv("EMERGENCY_PERIOD", 10 * 60))
EMERGENCY_DROP_PERCENT = Decimal(os.getenv("EMERGENCY_DROP_PERCENT", "0.10"))

# 부분 청산 비율 (변경 없음)
PARTIAL_EXIT_RATIO = Decimal(os.getenv("PARTIAL_EXIT_RATIO", "0.5"))

# 4. 요약 전송 설정 (Telegram) (변경 없음)
SUMMARY_TIMES = [
    (6, 30), (12, 0), (18, 0), (21, 30)
]

# 5. API 키 및 Telegram (변경 없음)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 환경 변수 검증 (변경 없음)
if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise RuntimeError("BINANCE API 키 또는 시크릿이 설정되지 않았습니다.")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("텔레그램 토큰 또는 챗 ID가 설정되지 않았습니다.")
