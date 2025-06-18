# strategy_pullback.py
from binance_api import get_price, get_klines
from utils import calculate_order_quantity
from position_manager import can_enter, open_positions, get_position
from order_manager import handle_entry, handle_exit
from risk_config import PULLBACK_TP_PERCENT, PULLBACK_SL_PERCENT

def calculate_ema(values, length):
    k = 2 / (length + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def check_entry(symbol):
    if not can_enter(symbol, "pullback"):
        return

    candles = get_klines(symbol, interval="5m", limit=30)
    if len(candles) < 30:
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

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "pullback":
        return

    pos = get_position(symbol)
    entry_price = pos["entry_price"]
    direction = pos["side"]
    price = get_price(symbol)
    if price is None:
        return

    tp = entry_price * (1 + PULLBACK_TP_PERCENT / 100) if direction == "long" else entry_price * (1 - PULLBACK_TP_PERCENT / 100)
    sl = entry_price * (1 - PULLBACK_SL_PERCENT / 100) if direction == "long" else entry_price * (1 + PULLBACK_SL_PERCENT / 100)

    if (direction == "long" and price >= tp) or (direction == "short" and price <= tp):
        reason = "TP"
    elif (direction == "long" and price <= sl) or (direction == "short" and price >= sl):
        reason = "SL"
    else:
        return

    handle_exit(symbol, "pullback", direction, pos["position_size"], entry_price, reason)