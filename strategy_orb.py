# strategy_orb.py
from datetime import datetime, timedelta
from binance_api import get_price, get_klines
from utils import calculate_order_quantity
from position_manager import can_enter, open_positions, get_position
from order_manager import handle_entry, handle_exit
from risk_config import ORB_TP_PERCENT, ORB_SL_PERCENT, ORB_TIMECUT_HOURS

def is_entry_time_kst():
    now = datetime.utcnow() + timedelta(hours=9)
    return (now.hour == 9 and now.minute < 60) or (now.hour == 21 and now.minute < 60)

def check_entry(symbol):
    if not is_entry_time_kst() or not can_enter(symbol, "orb"):
        return

    klines = get_klines(symbol, interval="1h", limit=2)
    if len(klines) < 2:
        return

    open_high = float(klines[-2][2])
    open_low = float(klines[-2][3])
    price = get_price(symbol)
    if price is None:
        return

    if price > open_high:
        direction = "long"
        side = "BUY"
    elif price < open_low:
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
        "strategy": "orb",
        "qty": qty,
        "tp_percent": ORB_TP_PERCENT,
        "sl_percent": ORB_SL_PERCENT
    }
    handle_entry(signal)

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "orb":
        return

    pos = get_position(symbol)
    entry_time = pos["entry_time"]
    entry_price = pos["entry_price"]
    direction = pos["side"]
    price = get_price(symbol)
    if price is None:
        return

    tp = entry_price * (1 + ORB_TP_PERCENT / 100) if direction == "long" else entry_price * (1 - ORB_TP_PERCENT / 100)
    sl = entry_price * (1 - ORB_SL_PERCENT / 100) if direction == "long" else entry_price * (1 + ORB_SL_PERCENT / 100)

    should_exit = False
    reason = ""

    if (direction == "long" and price >= tp) or (direction == "short" and price <= tp):
        reason = "TP"
        should_exit = True
    elif (direction == "long" and price <= sl) or (direction == "short" and price >= sl):
        reason = "SL"
        should_exit = True
    elif datetime.utcnow() - entry_time > timedelta(hours=ORB_TIMECUT_HOURS):
        reason = "TimeCut"
        should_exit = True

    if should_exit:
        handle_exit(symbol, "orb", direction, pos["position_size"], entry_price, reason)