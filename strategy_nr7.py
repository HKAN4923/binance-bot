# 파일명: strategy_nr7.py
# 라쉬케 전략: NR7 (Natural Range 7)
# core.py에서 공통 함수 import, order_manager의 handle_entry/exit 사용

from datetime import datetime, timedelta
from core import (
    get_klines,
    get_price,
    calculate_order_quantity,
    can_enter,
    get_open_positions,
    get_position
)
from order_manager import handle_entry, handle_exit
from risk_config import NR7_TP_PERCENT, NR7_SL_PERCENT, NR7_TIMECUT_HOURS

# NR7 전략 진입 체크 (1시간 봉 사용)
# 최근 8개의 봉 중 가장 좁은 변동폭(High-Low)인 7개 봉을 찾아
# 현재 가격이 해당 봉의 High를 상향 돌파하면 long,
# Low를 하향 돌파하면 short로 진입

def check_entry(symbol: str) -> None:
    # 중복 진입 방지
    if not can_enter(symbol, "nr7"):
        return

    klines = get_klines(symbol, interval="1h", limit=8)
    if not klines or len(klines) < 8:
        return

    # 최근 7개 봉(마지막 제외)에 대해 변동폭 계산
    bars = klines[:-1]
    ranges = [(float(bar[2]) - float(bar[3]), idx) for idx, bar in enumerate(bars)]
    # 가장 좁은 변동폭 봉 선택
    min_range, min_idx = min(ranges, key=lambda x: x[0])
    narrow_bar = bars[min_idx]
    narrow_high = float(narrow_bar[2])
    narrow_low = float(narrow_bar[3])

    # 현재 가격
    price = get_price(symbol)
    if price is None:
        return

    # 돌파 시그널 판단
    if price > narrow_high:
        direction = "long"
        side = "BUY"
    elif price < narrow_low:
        direction = "short"
        side = "SELL"
    else:
        return

    # 수량 계산
    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        return

    # 신호 생성 및 진입 처리
    signal = {
        "symbol": symbol,
        "side": side,
        "direction": direction,
        "strategy": "nr7",
        "qty": qty,
        "tp_percent": NR7_TP_PERCENT,
        "sl_percent": NR7_SL_PERCENT
    }
    handle_entry(signal)

# NR7 청산 체크
# TP/SL 도달 또는 지정된 시간 경과 시 청산

def check_exit(symbol: str) -> None:
    positions = get_open_positions()
    if symbol not in positions or positions[symbol]["strategy"] != "nr7":
        return

    pos = get_position(symbol)
    entry_time = pos.get("entry_time")
    entry_price = pos.get("entry_price")
    direction = pos.get("side")
    qty = pos.get("qty")
    price = get_price(symbol)
    if price is None:
        return

    # TP/SL 가격
    tp = entry_price * (1 + NR7_TP_PERCENT / 100) if direction == "long" else entry_price * (1 - NR7_TP_PERCENT / 100)
    sl = entry_price * (1 - NR7_SL_PERCENT / 100) if direction == "long" else entry_price * (1 + NR7_SL_PERCENT / 100)

    # 청산 사유 결정
    reason = None
    if (direction == "long" and price >= tp) or (direction == "short" and price <= tp):
        reason = "TP"
    elif (direction == "long" and price <= sl) or (direction == "short" and price >= sl):
        reason = "SL"
    else:
        # TimeCut 경과 확인
        if entry_time and datetime.utcnow() - entry_time > timedelta(hours=NR7_TIMECUT_HOURS):
            reason = "TimeCut"

    if reason:
        handle_exit(symbol, "nr7", direction, qty, entry_price, reason)
