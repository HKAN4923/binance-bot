# 파일명: strategy_pullback.py
# 라쉬케 전략: Pullback
# core.py에서 공통 함수 import, order_manager의 handle_entry/handle_exit 사용

from core import (
    get_klines,
    get_price,
    calculate_order_quantity,
    can_enter,
    get_open_positions,
    get_position
)
from order_manager import handle_entry, handle_exit
from risk_config import PULLBACK_TP_PERCENT, PULLBACK_SL_PERCENT

# Pullback 전략 로직: EMA 21 기준 가격 반등 진입

def calculate_ema(values, length):
    """
    단순 EMA 계산 함수 (pullback용)
    """
    k = 2 / (length + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def check_entry(symbol: str) -> None:
    """
    pullback 전략 진입 체크
    """
    if not can_enter(symbol, "pullback"):
        return

    candles = get_klines(symbol, interval="5m", limit=30)
    if not candles or len(candles) < 30:
        return

    closes = [float(c[4]) for c in candles]
    ema21 = calculate_ema(closes[-22:], 21)
    price = closes[-1]
    prev_price = closes[-2]

    if prev_price < ema21 < price:
        direction = "long"
        side = "BUY"
    elif prev_price > ema21 > price:
        direction = "short"
        side = "SELL"
    else:
        return

    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        return

    signal = {
        "symbol": symbol,
        "side": side,
        "direction": direction,
        "strategy": "pullback",
        "qty": qty,
        "tp_percent": PULLBACK_TP_PERCENT,
        "sl_percent": PULLBACK_SL_PERCENT
    }
    handle_entry(signal)


def check_exit(symbol: str) -> None:
    """
    pullback 전략 청산 체크
    """
    positions = get_open_positions()
    if symbol not in positions or positions[symbol]["strategy"] != "pullback":
        return

    pos = get_position(symbol)
    entry_price = pos["entry_price"]
    direction = pos["side"]
    qty = pos.get("qty", 0)
    price = get_price(symbol)
    if price is None:
        return

    tp = entry_price * (1 + PULLBACK_TP_PERCENT / 100) if direction == "long" else entry_price * (1 - PULLBACK_TP_PERCENT / 100)
    sl = entry_price * (1 - PULLBACK_SL_PERCENT / 100) if direction == "long" else entry_price * (1 + PULLBACK_SL_PERCENT / 100)

    # TP/SL 체크
    if (direction == "long" and price >= tp) or (direction == "short" and price <= tp):
        reason = "TP"
    elif (direction == "long" and price <= sl) or (direction == "short" and price >= sl):
        reason = "SL"
    else:
        return

    handle_exit(symbol, "pullback", direction, qty, entry_price, reason)
