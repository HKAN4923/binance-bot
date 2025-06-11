# strategy_ema_cross.py
from datetime import datetime, timedelta
from binance_api import get_price, get_klines, place_market_order, place_market_exit
from position_manager import can_enter, add_position, remove_position, open_positions
from utils import calculate_tp_sl, log_trade, now_string
from risk_config import EMA_TP_PERCENT, EMA_SL_PERCENT
from utils import calculate_order_quantity

def calculate_ema(values, length):
    k = 2 / (length + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(values, period=14):
    deltas = [values[i+1] - values[i] for i in range(len(values)-1)]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]

    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 0

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def check_entry(symbol):
    if not can_enter(symbol, "ema"):
        return

    candles = get_klines(symbol, interval="5m", limit=30)
    closes = [float(c[4]) for c in candles]
    ema9_prev = calculate_ema(closes[-21:-1], 9)
    ema21_prev = calculate_ema(closes[-21:-1], 21)
    ema9_now = calculate_ema(closes[-20:], 9)
    ema21_now = calculate_ema(closes[-20:], 21)

    rsi = calculate_rsi(closes[-15:], 14)
    price = closes[-1]

    if ema9_prev < ema21_prev and ema9_now > ema21_now and rsi > 50:
        direction = "long"
        side = "BUY"
    elif ema9_prev > ema21_prev and ema9_now < ema21_now and rsi < 50:
        direction = "short"
        side = "SELL"
    else:
        return

    qty = calculate_order_quantity(symbol)
    resp = place_market_order(symbol, side, qty)
    entry_price = float(resp["fills"][0]["price"])

    add_position(symbol, entry_price, "ema", direction, qty)
    tp, sl = calculate_tp_sl(entry_price, EMA_TP_PERCENT, EMA_SL_PERCENT, direction)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": "ema",
        "side": direction,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "status": "entry"
    })

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "ema":
        return

    pos = open_positions[symbol]
    entry_price = pos["entry_price"]
    side = pos["side"]
    price = get_price(symbol)

    tp, sl = calculate_tp_sl(entry_price, EMA_TP_PERCENT, EMA_SL_PERCENT, side)
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
            "strategy": "ema",
            "side": side,
            "exit_price": price,
            "entry_price": entry_price,
            "reason": reason,
            "status": "exit"
        })
