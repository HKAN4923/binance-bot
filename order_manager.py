# order_manager.py
from binance_api import (
    place_market_order,
    create_take_profit,
    create_stop_order,
    place_market_exit,
    get_price
)
from utils import calculate_tp_sl, extract_entry_price, now_string, summarize_trades, log_trade
from position_manager import add_position, remove_position
from telegram_bot import send_telegram

def handle_entry(signal):
    symbol = signal["symbol"]
    side = signal["side"]
    direction = signal["direction"]
    strategy = signal["strategy"]
    qty = signal["qty"]
    tp_percent = signal["tp_percent"]
    sl_percent = signal["sl_percent"]

    resp = place_market_order(symbol, side, qty)
    entry_price = extract_entry_price(resp)
    if entry_price is None:
        print(f"[{strategy.upper()}] {symbol} 주문 실패")
        return

    tp, sl = calculate_tp_sl(entry_price, tp_percent, sl_percent, direction)
    create_take_profit(symbol, "SELL" if direction == "long" else "BUY", qty, tp)
    create_stop_order(symbol, "SELL" if direction == "long" else "BUY", qty, sl)

    add_position(symbol, entry_price, strategy, direction, qty)

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": strategy,
        "side": direction,
        "entry_price": entry_price,
        "tp": tp,
        "sl": sl,
        "position_size": qty,
        "status": "entry"
    })

    send_telegram(
        f"✅ 진입: {symbol} ({direction}) @ {entry_price:.2f}\n"
        f"전략: {strategy.upper()} | 수량: {qty}\n"
        f"TP: {tp:.2f} / SL: {sl:.2f}"
    )

def handle_exit(symbol, strategy, direction, qty, entry_price, reason):
    price = get_price(symbol)
    if price is None:
        return

    place_market_exit(symbol, "SELL" if direction == "long" else "BUY", qty)
    remove_position(symbol)

    pl = (price - entry_price) * qty if direction == "long" else (entry_price - price) * qty
    emoji = "🟢" if pl >= 0 else "🔴"

    log_trade({
        "time": now_string(),
        "symbol": symbol,
        "strategy": strategy,
        "side": direction,
        "exit_price": price,
        "entry_price": entry_price,
        "reason": reason,
        "position_size": qty,
        "status": "exit"
    })

    send_telegram(
        f"{emoji} 청산: {symbol} ({direction}) @ {price:.2f}\n"
        f"손익: {pl:.2f} USDT | 전략: {strategy.upper()}"
    )
    send_telegram(summarize_trades())