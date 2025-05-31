import threading
import time
import logging
from utils import to_kst
from telegram_notifier import send_telegram
from config import SUMMARY_TIMES
from collections import deque

# trade_log: 거래 로그 리스트 (외부에서 전달받음)
#   예시 entry: {'timestamp': float, 'symbol': str, 'side': str, 'pnl_pct': float, 'pnl_usdt': float}
# trade_log_lock: threading.Lock()

def start_summary_scheduler(trade_log, trade_log_lock):
    threading.Thread(target=_summary_loop, args=(trade_log, trade_log_lock), daemon=True).start()


def _summary_loop(trade_log, trade_log_lock):
    last_sent = None  # (hour, minute) 형태로 마지막 전송 시각 기억
    while True:
        try:
            now = to_kst(time.time())
            hour = now.hour
            minute = now.minute
            for (h, m) in SUMMARY_TIMES:
                # 매 시각(시, 분)이 설정과 일치하고, 아직 전송되지 않았다면 요약 전송
                if hour == h and minute == m and last_sent != (h, m):
                    with trade_log_lock:
                        logs = list(trade_log)
                    if logs:
                        total_trades = len(logs)
                        win_trades = sum(1 for t in logs if t['pnl_pct'] > 0)
                        lose_trades = total_trades - win_trades
                        avg_pnl = sum(t['pnl_pct'] for t in logs) / total_trades
                        msg = (
                            f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\\n"
                            f"▶ Total Trades: {total_trades}\\n"
                            f"▶ Wins: {win_trades}\\n"
                            f"▶ Losses: {lose_trades}\\n"
                            f"▶ Avg PnL %: {avg_pnl:.2f}"
                        )
                    else:
                        msg = f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\\nNo trades in this period."
                    send_telegram(msg)
                    last_sent = (h, m)
            # 30초마다 체크
            time.sleep(30)
        except Exception as e:
            logging.error(f"Error in summary scheduler: {e}")
            time.sleep(30)
