# strategy_nr7.py
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
from risk_config import NR7_TP_PERCENT, NR7_SL_PERCENT, NR7_TIMECUT_HOURS

def is_entry_time_kst():
    now = datetime.utcnow() + timedelta(hours=9)
    return (now.hour == 9 and now.minute < 60) or (now.hour == 21 and now.minute < 60)

def check_entry(symbol):
    if not is_entry_time_kst() or not can_enter(symbol, "nr7"):
        return

    klines = get_klines(symbol, interval="1d", limit=8)
    if len(klines) < 8:
        return

    ranges = [(float(k[2]) - float(k[3])) for k in klines[:-1]]
    min_range_index = ranges.index(min(ranges))
    if min_range_index != 6:
        return

    prev_kline = klines[-2]
    high = float(prev_kline[2])
    low = float(prev_kline[3])
    price = get_price(symbol)

    if price > high:
        side = "BUY"
        direction = "long"
    elif price < low:
        side = "SELL"
        direction = "short"
    else:
        return

    qty = calculate_order_quantity(symbol)
    if qty <= 0:
        print(f"[NR7] {symbol} 주문 스킵: 수량(qty)={qty}")
        return

    resp = place_market_order(symbol, side, qty)
    entry_price = extract_entry_price(resp)
    if entry_price is None:
        print(f"[NR7] {symbol} 주문 실패: {resp}")
        return

    add_position(symbol, entry_price, "nr7", direction, qty)
    tp, sl = calculate_tp_sl(entry_price, NR7_TP_PERCENT, NR7_SL_PERCENT, direction)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": "nr7",
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
        f"전략: NR7 | 수량: {qty}\n"
        f"TP: {tp:.2f} / SL: {sl:.2f}"
    )
    send_telegram(message)

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "nr7":
        return

    pos = open_positions[symbol]
    entry_time = pos["entry_time"]
    entry_price = pos["entry_price"]
    side = pos["side"]
    price = get_price(symbol)

    tp, sl = calculate_tp_sl(entry_price, NR7_TP_PERCENT, NR7_SL_PERCENT, side)
    should_exit = False
    reason = ""

    if (side == "long" and price >= tp) or (side == "short" and price <= tp):
        reason = "TP"
        should_exit = True
    elif (side == "long" and price <= sl) or (side == "short" and price >= sl):
        reason = "SL"
        should_exit = True
    elif datetime.utcnow() - entry_time > timedelta(hours=NR7_TIMECUT_HOURS):
        reason = "TimeCut"
        should_exit = True

    if should_exit:
        qty = pos["position_size"]
        place_market_exit(symbol, "SELL" if side == "long" else "BUY", qty)
        remove_position(symbol)

        log_trade({
            "time": now_string(),
            "symbol": symbol,
            "strategy": "nr7",
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
            f"손익: {pl:.2f} USDT | 전략: NR7"
        )
        send_telegram(result_msg)

        summary = summarize_trades()
        send_telegram(summary)
