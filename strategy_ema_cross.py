# strategy_ema_cross.py
from binance_api import (
    get_price, get_klines,
    place_market_order, place_market_exit,
    create_take_profit, create_stop_order
)
from position_manager import can_enter, add_position, remove_position, open_positions
from utils import (
    calculate_tp_sl,
    log_trade,
    now_string,
    calculate_order_quantity,
    extract_entry_price,
    summarize_trades,
    calculate_rsi
)
from telegram_bot import send_telegram
from risk_config import EMA_TP_PERCENT, EMA_SL_PERCENT

def calculate_ema(values, length):
    k = 2 / (length + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema

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
    if qty <= 0:
        print(f"[EMA] {symbol} 주문 스킵: 수량(qty)={qty}")
        return

    resp = place_market_order(symbol, side, qty)
    entry_price = extract_entry_price(resp)
    if entry_price is None:
        print(f"[EMA] {symbol} 주문 실패")
        return

    tp, sl = calculate_tp_sl(entry_price, EMA_TP_PERCENT, EMA_SL_PERCENT, direction)
    create_take_profit(symbol, "SELL" if direction == "long" else "BUY", qty, tp)
    create_stop_order(symbol, "SELL" if direction == "long" else "BUY", qty, sl)

    add_position(symbol, entry_price, "ema", direction, qty)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": "ema",
        "side": direction,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "position_size": qty,
        "status": "entry"
    })

    message = (
        f"✅ 진입: {symbol} ({direction}) @ {entry_price:.2f}\n"
        f"전략: EMA | 수량: {qty}\n"
        f"TP: {tp:.2f} / SL: {sl:.2f}"
    )
    send_telegram(message)

def check_exit(symbol):
    if symbol not in open_positions or open_positions[symbol]["strategy"] != "ema":
        return

    pos = open_positions[symbol]
    entry_price = pos["entry_price"]
    side = pos["side"]
    price = get_price(symbol)
    if price is None:
        return

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
            "position_size": qty,
            "status": "exit"
        })

        pl = (price - entry_price) * qty if side == "long" else (entry_price - price) * qty
        emoji = "🟢" if pl >= 0 else "🔴"
        send_telegram(
            f"{emoji} 청산: {symbol} ({side}) @ {price:.2f}\n"
            f"손익: {pl:.2f} USDT | 전략: EMA"
        )
        send_telegram(summarize_trades())
