# strategy_orb.py
from datetime import datetime, timedelta
from binance_api import get_price, get_klines, place_market_order, place_market_exit
from position_manager import can_enter, add_position, remove_position, open_positions
from utils import (
    calculate_tp_sl,
    log_trade,
    now_string,
    calculate_order_quantity,
    extract_entry_price,
    summarize_trades
)
from telegram_bot import send_telegram
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

    opening_candle = klines[-2]
    open_high = float(opening_candle[2])
    open_low = float(opening_candle[3])
    price = get_price(symbol)

    if price > open_high:
        side = "BUY"
        direction = "long"
    elif price < open_low:
        side = "SELL"
        direction = "short"
    else:
        return

    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        print(f"[ORB] {symbol} 주문 스킵: 수량(qty)={qty}")
        return

    resp = place_market_order(symbol, side, qty)
    entry_price = extract_entry_price(resp)
    if entry_price is None:
        print(f"[ORB] {symbol} 주문 실패: {resp}")
        return

    add_position(symbol, entry_price, "orb", direction, qty)
    tp, sl = calculate_tp_sl(entry_price, ORB_TP_PERCENT, ORB_SL_PERCENT, direction)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": "orb",
        "side": direction,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "position_size": qty,
        "status": "entry"
    })

    # ✅ 텔레그램 진입 알림
    message = (
        f"✅ 진입: {symbol} ({direction}) @ {entry_price:.2f}\n"
        f"전략: ORB | 수량: {qty}\n"
        f"TP: {tp:.2f} / SL: {sl:.2f}"
    )
    send_telegram(message)

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "orb":
        return

    pos = open_positions[symbol]
    entry_time = pos["entry_time"]
    entry_price = pos["entry_price"]
    side = pos["side"]
    price = get_price(symbol)

    tp, sl = calculate_tp_sl(entry_price, ORB_TP_PERCENT, ORB_SL_PERCENT, side)
    should_exit = False
    reason = ""

    if (side == "long" and price >= tp) or (side == "short" and price <= tp):
        reason = "TP"
        should_exit = True
    elif (side == "long" and price <= sl) or (side == "short" and price >= sl):
        reason = "SL"
        should_exit = True
    elif datetime.utcnow() - entry_time > timedelta(hours=ORB_TIMECUT_HOURS):
        reason = "TimeCut"
        should_exit = True

    if should_exit:
        qty = pos["position_size"]
        place_market_exit(symbol, "SELL" if side == "long" else "BUY", qty)
        remove_position(symbol)

        log_trade({
            "time": now_string(),
            "symbol": symbol,
            "strategy": "orb",
            "side": side,
            "exit_price": price,
            "entry_price": entry_price,
            "reason": reason,
            "position_size": qty,
            "status": "exit"
        })

        # ✅ 텔레그램 청산 알림 + 누적 통계
        pl = (price - entry_price) * qty if side == "long" else (entry_price - price) * qty
        emoji = "🟢" if pl >= 0 else "🔴"
        result_msg = (
            f"{emoji} 청산: {symbol} ({side}) @ {price:.2f}\n"
            f"손익: {pl:.2f} USDT | 전략: ORB"
        )
        send_telegram(result_msg)

        summary = summarize_trades()
        send_telegram(summary)
