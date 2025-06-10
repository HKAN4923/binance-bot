# trade_summary.py
import threading
import time
import logging
import pandas as pd
import matplotlib.pyplot as plt
from collections import deque
from utils import to_kst
from telegram_notifier import send_telegram, send_telegram_photo
from config import SUMMARY_TIMES

# trade_log: 거래 로그 리스트 (외부에서 전달받음)
#   예시 entry: {'timestamp': float, 'symbol': str, 'side': str, 'pnl_pct': float, 'pnl_usdt': float}
# trade_log_lock: threading.Lock()

def start_summary_scheduler(trade_log, trade_log_lock):
    threading.Thread(target=_summary_loop, args=(trade_log, trade_log_lock), daemon=True).start()

def _summary_loop(trade_log, trade_log_lock):
    last_sent = None
    while True:
        try:
            now = to_kst(time.time())
            hour = now.hour
            minute = now.minute
            for (h, m) in SUMMARY_TIMES:
                if hour == h and minute == m and last_sent != (h, m):
                    with trade_log_lock:
                        logs = list(trade_log)
                    if logs:
                        df = pd.DataFrame(logs)
                        total_trades = len(df)
                        win_trades = (df['pnl_pct'] > 0).sum()
                        lose_trades = total_trades - win_trades
                        avg_pnl = df['pnl_pct'].mean()
                        total_pnl_usdt = df['pnl_usdt'].sum()
                        # Equity Curve
                        df['cumulative_pnl'] = df['pnl_usdt'].cumsum()
                        plt.figure()
                        plt.plot(df['cumulative_pnl'])
                        plt.title('Equity Curve')
                        plt.xlabel('Trade Index')
                        plt.ylabel('Cumulative PnL (USDT)')
                        img_path = f"/mnt/data/equity_curve_{h}_{m}.png"
                        plt.savefig(img_path)
                        plt.close()
                        msg = (
                            f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\\n"
                            f"▶ Total Trades: {total_trades}\\n"
                            f"▶ Wins: {win_trades}\\n"
                            f"▶ Losses: {lose_trades}\\n"
                            f"▶ Avg PnL %: {avg_pnl:.2f}\\n"
                            f"▶ Total PnL (USDT): {total_pnl_usdt:.2f}"
                        )
                        send_telegram(msg)
                        send_telegram_photo(img_path, caption="📈 Equity Curve")
                    else:
                        msg = f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\\nNo trades in this period."
                        send_telegram(msg)
                    last_sent = (h, m)
            time.sleep(30)
        except Exception as e:
            logging.error(f"Error in summary scheduler: {e}")
            time.sleep(30)
