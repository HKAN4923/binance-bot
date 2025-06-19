# 파일명: strategy_orb.py
# 라쉬케 전략: ORB (Opening Range Breakout)
# 롱 진입만 허용 (숏 진입 무시하여 실전 승률 강화)

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
from risk_config import ORB_TP_PERCENT, ORB_SL_PERCENT, ORB_TIMECUT_HOURS


# 진입 가능 시간 (KST 기준 09:00~10:00, 21:00~22:00)
def is_entry_time_kst():
    now = datetime.utcnow() + timedelta(hours=9)
    return (now.hour == 9 and now.minute < 60) or (now.hour == 21 and now.minute < 60)


# Entry 조건 검사 (롱 진입만 허용)
def check_entry(symbol: str) -> None:
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

    # 롱 진입만 허용
    if price > open_high:
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
        "strategy": "orb",
        "qty": qty,
        "tp_percent": ORB_TP_PERCENT,
        "sl_percent": ORB_SL_PERCENT
    }
    handle_entry(signal)


# Exit 조건 검사
def check_exit(symbol: str) -> None:
    positions = get_open_positions()
    if symbol not in positions or positions[symbol]["strategy"] != "orb":
        return

    pos = get_position(symbol)
    entry_time = pos["entry_time"]
    entry_price = pos["entry_price"]
    direction = pos["side"]
    price = get_price(symbol)
    if price is None:
        return

    tp = entry_price * (1 + ORB_TP_PERCENT / 100)
    sl = entry_price * (1 - ORB_SL_PERCENT / 100)

    should_exit = False
    reason = ""

    if price >= tp:
        reason = "TP"
        should_exit = True
    elif price <= sl:
        reason = "SL"
        should_exit = True
    elif datetime.utcnow() - entry_time > timedelta(hours=ORB_TIMECUT_HOURS):
        reason = "TimeCut"
        should_exit = True

    if should_exit:
        qty = pos.get("qty")
        handle_exit(symbol, "orb", direction, qty, entry_price, reason)
