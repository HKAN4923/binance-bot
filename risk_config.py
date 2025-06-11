# risk_config.py
# 모든 전략에서 사용할 공통 리스크 및 설정값 정의

# === 기본 거래 설정 ===
LEVERAGE = 1  # 기본 레버리지 (전략별로 바꿀 수 있음)
POSITION_RATIO = 0.2  # 자산의 20%만 진입

# === ORB 전략 설정 ===
ORB_TP_PERCENT = 2.0  # 익절 2%
ORB_SL_PERCENT = 1.0  # 손절 1%
ORB_TIMECUT_HOURS = 3  # 3시간 후 무조건 청산

# === NR7 전략 설정 ===
NR7_TP_PERCENT = 1.8
NR7_SL_PERCENT = 0.9
NR7_TIMECUT_HOURS = 3

# === PULLBACK 전략 설정 ===
PULLBACK_TP_PERCENT = 1.2
PULLBACK_SL_PERCENT = 0.8
PULLBACK_REENTRY_TIMEOUT_MINUTES = 60  # 동일 심볼 재진입 쿨타임 (분)

# === EMA 전략 설정 ===
EMA_TP_PERCENT = 1.2
EMA_SL_PERCENT = 0.8
EMA_REENTRY_TIMEOUT_MINUTES = 60

# === 기타 설정 ===
MAX_POSITION_COUNT = 5  # 최대 동시에 보유할 포지션 수
