# main.py
import threading
import time
from binance_client import set_leverage, get_klines, place_order, set_sl_tp
from config import SYMBOLS
from strategy import check_entry
from utils import calculate_atr, calculate_quantity
from telegram_notifier import send_message
from trade_summary import trade_summary
from position_monitor import monitor_positions, heartbeat

if __name__ == '__main__':
    # 설정
    set_leverage(SYMBOLS)
    send_message("🤖 Bot started: Linda Raschke strategies activated.")

    # 모니터 스레드
    threading.Thread(target=monitor_positions, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()

    # 메인 트레이딩 루프
    while True:
        for sym in SYMBOLS:
            df = get_klines(sym, '1m', limit=100)
            sig = check_entry(df)
            if sig:
                qty = calculate_quantity(sym)
                order = place_order(sym, sig, qty)
                entry_price = float(order['avgFillPrice'])
                atr = calculate_atr(df).iloc[-1]
                if sig == 'BUY':
                    sl = entry_price - atr
                    tp = entry_price + atr
                    side = 'SELL'
                else:
                    sl = entry_price + atr
                    tp = entry_price - atr
                    side = 'BUY'
                set_sl_tp(sym, side, sl_price=round(sl, 2), tp_price=round(tp, 2), quantity=qty)
                send_message(
                    f"✏️ Entry {sig} {sym}\nqty={qty}\nentry={entry_price:.2f} SL={sl:.2f} TP={tp:.2f}"
                )
        time.sleep(5)
