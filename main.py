import threading
import time
from datetime import timedelta
from binance.enums import SIDE_BUY, SIDE_SELL
from binance_client      import *
from strategy           import check_entry
from telegram_notifier  import send_telegram
from utils              import to_kst, calculate_qty

# ─── 설정 ─────────────────────────────────────────────────────────────────────
LEVERAGE                 = 10
LOSS_THRESHOLD           = 0.015
PROFIT_TARGET            = 0.03
MAX_TRADE_DURATION       = 2 * 60 * 60
RECHECK_TIME             = 1.5 * 60 * 60
POSITION_CHECK_INTERVAL  = 1
ANALYSIS_INTERVAL_SEC    = 1

positions = {}  # symbol → { side, entry_price, quantity, entry_time, notified }

# ─── 포지션 모니터링 ───────────────────────────────────────────────────────────
def monitor_positions():
    while True:
        now = time.time()
        for sym, pos in list(positions.items()):
            try:
                mark = get_mark_price(sym)
                entry = pos['entry_price']
                pnl   = (mark-entry)/entry if pos['side']=="long" else (entry-mark)/entry
                elapsed = now - pos['entry_time']

                if pnl >= PROFIT_TARGET or pnl <= -LOSS_THRESHOLD or elapsed >= MAX_TRADE_DURATION:
                    side_op = SIDE_SELL if pos['side']=="long" else SIDE_BUY
                    create_market_order(sym, side_op, pos['quantity'])
                    send_telegram(f"🔸 EXIT {sym} | PnL: {pnl*100:.2f}%")
                    del positions[sym]
                    continue

                if elapsed >= RECHECK_TIME and not pos['notified']:
                    send_telegram(f"⏱️ HOLDING {sym} | Current PnL: {pnl*100:.2f}%")
                    pos['notified'] = True

                if int(now) % 30 == 0:
                    print(f"[{sym}] 감시중... PnL: {pnl*100:.2f}% | 경과: {int(elapsed)}s")
            except Exception as e:
                print(f"[{sym}] 모니터링 오류:", e)
        time.sleep(POSITION_CHECK_INTERVAL)

# ─── 시장 분석 ────────────────────────────────────────────────────────────────
def analyze_market():
    last_log = time.time()
    while True:
        symbols = get_all_symbols()
        total   = len(symbols)
        open_cnt= len(positions)
        # 1분에 한 번 터미널에 현황 출력
        if time.time() - last_log >= 60:
            print(f"{to_kst()} 종목 찾는중...({open_cnt}/{total})")
            last_log = time.time()

        for idx, sym in enumerate(symbols, start=1):
            if sym in positions:
                continue
            df = get_ohlcv(sym)
            if df is None:
                continue
            sig = check_entry(df)
            if sig:
                # 레버리지·수량 설정
                change_leverage(sym, LEVERAGE)
                bal   = get_balance()
                price = get_mark_price(sym)
                p_price, p_qty = get_precision(sym)
                qty   = calculate_qty(bal, price, LEVERAGE, 0.1, p_qty)

                # 진입 주문
                ordr = create_market_order(sym, SIDE_BUY if sig=="long" else SIDE_SELL, qty)
                entry_price = float(ordr.get('avgFillPrice') or price)
                # TP/SL
                atr = entry_price * 0.005
                tp  = round(entry_price + atr*3 if sig=="long" else entry_price - atr*3, p_price)
                sl  = round(entry_price - atr*1.5 if sig=="long" else entry_price + atr*1.5, p_price)
                create_take_profit(sym, SIDE_SELL if sig=="long" else SIDE_BUY, tp, qty)
                create_stop_order(sym, SIDE_SELL if sig=="long" else SIDE_BUY, sl, qty)

                positions[sym] = {
                    'side': sig,
                    'entry_price': entry_price,
                    'quantity': qty,
                    'entry_time': time.time(),
                    'notified': False
                }
                send_telegram(f"🔹 ENTRY {sym} | {sig.upper()}\n"
                              f"Entry: {entry_price:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}")

        time.sleep(ANALYSIS_INTERVAL_SEC)

# ─── 메인 ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Bot started")
    send_telegram("🤖 Bot started")

    threading.Thread(target=monitor_positions, daemon=True).start()
    threading.Thread(target=analyze_market, daemon=True).start()

    while True:
        time.sleep(60)