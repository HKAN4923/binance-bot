# risk_config.py

# 포지션 설정
POSITION_RATIO = 0.25  # 내 총 자산의 25% 사용
LEVERAGE = 5           # 5배 레버리지
MAX_POSITIONS = 5      # 최대 동시 포지션 수

# 전략별 TP/SL 및 타임컷 설정 (% 단위)
ORB_TP_PERCENT = 2
ORB_SL_PERCENT = 1
ORB_TIMECUT_HOURS = 3

NR7_TP_PERCENT = 2
NR7_SL_PERCENT = 1
NR7_TIMECUT_HOURS = 3

EMA_TP_PERCENT = 1.8
EMA_SL_PERCENT = 1.2

PULLBACK_TP_PERCENT = 1.2
PULLBACK_SL_PERCENT = 0.8

# ✅ 최소 주문 금액 설정
MIN_NOTIONAL = 5.0  # 바이낸스 선물 최소 주문 금액 USDT 기준
