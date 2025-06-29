"""리스크 설정 파일"""

# 최대 동시 포지션 수
MAX_POSITIONS = 4

# 포지션당 자산 사용 비율 (ex: 0.2 = 전체 자산의 20%)
CAPITAL_USAGE = 0.25

# 레버리지 (1~125 범위)
LEVERAGE = 5

# 포지션 유지 최대 시간 (단위: 분) → 초과 시 강제 청산
TIME_CUT_MINUTES = 120  

# ORB, NR7 전략을 위한 예약 슬롯 수
RESERVED_SLOTS = 0

# 진입 후 동일 심볼/전략 재진입 금지 시간 (단위: 분)
COOLDOWN_MINUTES = 30

# TP/SL 설정 방식
USE_MARKET_TP_SL = False           # 기본: 지정가 TP/SL
USE_MARKET_TP_SL_BACKUP = True      # 지정가 실패 시 감시 후 시장가 청산으로 대체

# TP/SL 기준 슬리피지 비율 (지정가로 설정 시 여유 범위)
TP_SL_SLIPPAGE_RATE = 0.02

# 전략별 TP/SL 비율 (%)
TP_SL_SETTINGS = {
    "ORB": {"tp": 0.025, "sl": 0.015},
    "NR7": {"tp": 0.015, "sl": 0.010},
    "EMA": {"tp": 0.020, "sl": 0.020},
    "HOLY_GRAIL": {"tp": 0.012, "sl": 0.008},
}

# 전략별 Time Cut 설정 (단위: 분)
TIME_CUT_BY_STRATEGY = {
    "ORB": 120,
    "NR7": 120,
    "EMA": 60,
    "HOLY_GRAIL": 45,
}
