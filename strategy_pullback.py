# strategy_pullback.py
from datetime import datetime, timedelta
from binance_api import get_price, get_klines, place_market_order, place_market_exit
from position_manager import can_enter, add_position, remove_position, open_positions
from utils import (
    calculate_tp_sl,
    log_trade,
    now_string,
    calculate_order_quantity,
    extract_entry_price,
)
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
    closes = [float(c[4]) for c in candles]
    ema21 = calculate_ema(closes[-22:], 21)
    price = closes[-1]
    prev_price = closes[-2]

    if price > ema21:
        direction = "long"
        side = "BUY"
    elif price < ema21:
        direction = "short"
        side = "SELL"
    else:
        return

    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        print(f"[Pullback] {symbol} 주문 스킵: 수량(qty)={qty}")
        return

    resp = place_market_order(symbol, side, qty)
    entry_price = extract_entry_price(resp)
    if entry_price is None:
        print(f"[Pullback] {symbol} 주문 실패: {resp}")
        return

    add_position(symbol, entry_price, "pullback", direction, qty)
    tp, sl = calculate_tp_sl(entry_price, PULLBACK_TP_PERCENT, PULLBACK_SL_PERCENT, direction)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": "pullback",
        "side": direction,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "status": "entry"
    })

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "pullback":
        return

    pos = open_positions[symbol]
    entry_price = pos["entry_price"]
    side = pos["side"]
    price = get_price(symbol)

    tp, sl = calculate_tp_sl(entry_price, PULLBACK_TP_PERCENT, PULLBACK_SL_PERCENT, side)
    should_exit = False
    reason = ""

    if (side == "long" and price >= tp) or (side == "short" and price <= tp):
        reason = "TP"
        should_exit = True
    elif (side == "long" and price <= sl) or (side == "short" and price >= sl):
        reason = "SL"
        should_exit = True

    if should_exit:
        qty = pos["position_size"]
        place_market_exit(symbol, "SELL" if side == "long" else "BUY", qty)
        remove_position(symbol)

        log_trade({
            "time": now_string(),
            "symbol": symbol,
            "strategy": "pullback",
            "side": side,
            "exit_price": price,
            "entry_price": entry_price,
            "reason": reason,
            "status": "exit"
        })
