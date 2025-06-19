# 파일명: risk_config.py
# 리스크 및 전략별 파라미터 설정 모듈

import os
from decimal import Decimal
from dotenv import load_dotenv
from decimal import Decimal


load_dotenv()

# ─────────── 포지션 사이즈 및 레버리지 ───────────
# 전체 자산 중 포지션당 사용할 비율 (예: 0.2 → 20%)
POSITION_RATIO = Decimal(os.getenv("POSITION_RATIO", "0.2"))
# 사용 레버리지 (예: 10배)
LEVERAGE = int(os.getenv("LEVERAGE", "10"))
# 최소 거래 가치(USDT 단위)
MIN_NOTIONAL = Decimal(os.getenv("MIN_NOTIONAL", "10"))

# ───────────── ORB 전략 파라미터 ─────────────
# 익절 비율(%)
ORB_TP_PERCENT = Decimal(os.getenv("ORB_TP_PERCENT", "1.75"))
# 손절 비율(%)
ORB_SL_PERCENT = Decimal(os.getenv("ORB_SL_PERCENT", "0.8"))
# 타임컷 (시간 단위)
ORB_TIMECUT_HOURS = int(os.getenv("ORB_TIMECUT_HOURS", "3"))

# ───────────── NR7 전략 파라미터 ─────────────
NR7_TP_PERCENT = Decimal(os.getenv("NR7_TP_PERCENT", "2"))
NR7_SL_PERCENT = Decimal(os.getenv("NR7_SL_PERCENT", "1"))
NR7_TIMECUT_HOURS = int(os.getenv("NR7_TIMECUT_HOURS", "3"))

# ───────── Pullback 전략 파라미터 ─────────
PULLBACK_TP_PERCENT = Decimal(os.getenv("PULLBACK_TP_PERCENT", "1.5"))
PULLBACK_SL_PERCENT = Decimal(os.getenv("PULLBACK_SL_PERCENT", "1"))

# ──────── EMA Cross 전략 파라미터 ─────────
EMA_TP_PERCENT = Decimal(os.getenv("EMA_TP_PERCENT", "1.5"))
EMA_SL_PERCENT = Decimal(os.getenv("EMA_SL_PERCENT", "1"))
EMA_SHORT_LEN_CROSS = int(os.getenv("EMA_SHORT_LEN_CROSS", "9"))
EMA_LONG_LEN_CROSS = int(os.getenv("EMA_LONG_LEN_CROSS", "21"))
EMA_TIMECUT_HOURS = int(os.getenv("EMA_TIMECUT_HOURS", "3"))

# ─────── 환경 변수 필수 확인 ─────────
for var in ["BINANCE_API_KEY", "BINANCE_API_SECRET", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]:
    if not os.getenv(var):
        raise RuntimeError(f"환경 변수 {var}가 설정되지 않았습니다.")
