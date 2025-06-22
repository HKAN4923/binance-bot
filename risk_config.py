# risk_config.py

import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

# -----------------------------
# 1) 레버리지 설정 (기본 1배, 필요 시 .env로 조정)
# -----------------------------
ORB_LEVERAGE        = int(os.getenv("ORB_LEVERAGE", "1"))
NR7_LEVERAGE        = int(os.getenv("NR7_LEVERAGE", "1"))
EMA_LEVERAGE        = int(os.getenv("EMA_LEVERAGE", "1"))
PULLBACK_LEVERAGE   = int(os.getenv("PULLBACK_LEVERAGE", "1"))

def get_leverage(strategy_name: str) -> int:
    return {
        "ORB":      ORB_LEVERAGE,
        "NR7":      NR7_LEVERAGE,
        "EMA":      EMA_LEVERAGE,
        "Pullback": PULLBACK_LEVERAGE,
    }.get(strategy_name, 1)


# -----------------------------
# 2) ORB 전략 리스크/시간 설정
# -----------------------------
ORB_SL_PERCENT       = Decimal(os.getenv("ORB_SL_PERCENT", "1.2"))   # 손절 1.2%
ORB_TP_PERCENT       = Decimal(os.getenv("ORB_TP_PERCENT", "2.4"))   # 익절 2.4%
ORB_TIMECUT_HOURS    = int(os.getenv("ORB_TIMECUT_HOURS", "2"))      # 타임컷 2시간


# -----------------------------
# 3) NR7 전략 리스크/시간 설정
# -----------------------------
NR7_SL_PERCENT       = Decimal(os.getenv("NR7_SL_PERCENT", "0.8"))   # 손절 0.8%
NR7_TP_PERCENT       = Decimal(os.getenv("NR7_TP_PERCENT", "1.6"))   # 익절 1.6%
NR7_TIMECUT_HOURS    = int(os.getenv("NR7_TIMECUT_HOURS", "2"))      # 타임컷 2시간


# -----------------------------
# 4) EMA 크로스 + RSI 전략 파라미터
# -----------------------------
EMA_FAST_PERIOD      = int(os.getenv("EMA_FAST_PERIOD", "8"))        # 빠른 EMA 기간
EMA_SLOW_PERIOD      = int(os.getenv("EMA_SLOW_PERIOD", "21"))       # 느린 EMA 기간
RSI_PERIOD           = int(os.getenv("RSI_PERIOD", "14"))           # RSI 계산 기간
EMA_RSI_LONG_MIN     = Decimal(os.getenv("EMA_RSI_LONG_MIN", "55"))  # 롱 진입 시 최소 RSI
EMA_RSI_SHORT_MAX    = Decimal(os.getenv("EMA_RSI_SHORT_MAX", "45")) # 숏 진입 시 최대 RSI
EMA_SL_PERCENT       = Decimal(os.getenv("EMA_SL_PERCENT", "1.5"))   # 손절 1.5%
EMA_TP_PERCENT       = Decimal(os.getenv("EMA_TP_PERCENT", "3.0"))   # 익절 3.0%
EMA_TIMECUT_HOURS    = int(os.getenv("EMA_TIMECUT_HOURS", "2"))      # 타임컷 2시간


# -----------------------------
# 5) Pullback 전략 리스크/시간 설정
# -----------------------------
PULLBACK_SL_PERCENT      = Decimal(os.getenv("PULLBACK_SL_PERCENT", "1.0"))  # 손절 1.0%
PULLBACK_TP_PERCENT      = Decimal(os.getenv("PULLBACK_TP_PERCENT", "2.0"))  # 익절 2.0%
PULLBACK_TIMECUT_HOURS   = int(os.getenv("PULLBACK_TIMECUT_HOURS", "2"))     # 타임컷 2시간
