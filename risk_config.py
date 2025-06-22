"""리스크 설정 파일"""

# 최대 동시 포지션 수
MAX_POSITIONS = 5

# 포지션당 자산 사용 비율 (ex: 0.2 = 전체 자산의 20%)
CAPITAL_USAGE = 0.2

# 레버리지 (1~125 범위)
LEVERAGE = 5

# 포지션 유지 최대 시간 (단위: 분) → 초과 시 강제 청산
TIME_CUT_MINUTES = 120

# ORB, NR7 전략을 위한 예약 슬롯 수
RESERVED_SLOTS = 0

# 진입 후 동일 심볼/전략 재진입 금지 시간 (단위: 분)
COOLDOWN_MINUTES = 30

# TP/SL 설정 방식
USE_MARKET_TP_SL = False             # 기본: 지정가 TP/SL
USE_MARKET_TP_SL_BACKUP = True      # 지정가 실패 시 감시 후 시장가 청산으로 대체

# TP/SL 기준 슬리피지 비율 (지정가로 설정 시 여유 범위)
TP_SL_SLIPPAGE_RATE = 0.02

