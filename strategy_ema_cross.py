# 파일명: strategy_ema_cross.py
# 라쉬케 전략: EMA 크로스 (롱 진입만 허용)

from core import (
    get_klines,
    get_price,
    calculate_order_quantity,
    can_enter,
    get_open_positions,
    get_position
)
from order_manager import handle_entry, handle_exit
from risk_config import EMA_TP_PERCENT, EMA_SL_PERCENT, EMA_SHORT_LEN_CROSS, EMA_LONG_LEN_CROSS, EMA_TIMECUT_HOURS
from datetime import datetime, timedelta


def calculate_ema(prices: list, length: int) -> float:
    """
    단순 EMA 계산 (가격 리스트, 길이)
    """
    k = 2 / (length + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def check_entry(symbol: str) -> None:
    if not can_enter(symbol, "ema"):
        return

    candles = get_klines(symbol, interval="5m", limit=50)
    if not candles or len(candles) < max(EMA_SHORT_LEN_CROSS, EMA_LONG_LEN_CROSS) + 1:
        return

    closes = [float(c[4]) for c in candles]
    ema_short = calculate_ema(closes[-(EMA_SHORT_LEN_CROSS+1):], EMA_SHORT_LEN_CROSS)
    ema_long = calculate_ema(closes[-(EMA_LONG_LEN_CROSS+1):], EMA_LONG_LEN_CROSS)

    # 롱 진입만 허용 (골든크로스)
    if ema_short > ema_long:
        direction = "long"
        side = "BUY"
    else:
        return  # 숏은 무시

    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        return

    signal = {
        "symbol": symbol,
        "side": side,
        "direction": direction,
        "strategy": "ema",
        "qty": qty,
        "tp_percent": EMA_TP_PERCENT,
        "sl_percent": EMA_SL_PERCENT
    }
    handle_entry(signal)


def check_exit(symbol: str) -> None:
    positions = get_open_positions()
    if symbol not in positions or positions[symbol]["strategy"] != "ema":
        return

    pos = get_position(symbol)
    entry_time = pos["entry_time"]
    entry_price = pos["entry_price"]
    direction = pos["side"]
    qty = pos.get("qty", 0)
    price = get_price(symbol)
    if price is None:
        return

    tp = entry_price * (1 + EMA_TP_PERCENT / 100)
    sl = entry_price * (1 - EMA_SL_PERCENT / 100)

    should_exit = False
    reason = ""

    if price >= tp:
        reason = "TP"
        should_exit = True
    elif price <= sl:
        reason = "SL"
        should_exit = True
    elif datetime.utcnow() - entry_time > timedelta(hours=EMA_TIMECUT_HOURS):
        reason = "TimeCut"
        should_exit = True

    if should_exit:
        handle_exit(symbol, "ema", direction, qty, entry_price, reason)
