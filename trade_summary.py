# 파일명: trade_summary.py
# 거래 요약 스케줄러 모듈
# 일정 시각마다 누적 손익 요약을 텔레그램으로 전송합니다.

import threading
import time
import logging
import pandas as pd
import matplotlib.pyplot as plt
from utils import to_kst
from telegram_bot import send_telegram, send_telegram_photo
from config import SUMMARY_TIMES

# 모듈 내부에 거래 로그 관리
trade_log = []
trade_log_lock = threading.Lock()


def add_trade_entry(entry: dict) -> None:
    """메인 코드에서 trade_log 기록 시 호출"""
    with trade_log_lock:
        trade_log.append(entry)


def start_summary_scheduler() -> None:
    """
    SUMMARY_TIMES에 지정된 시각마다 요약 전송 스레드 시작
    """
    threading.Thread(target=_summary_loop, daemon=True).start()


def _summary_loop() -> None:
    last_sent = None
    while True:
        try:
            now = to_kst(time.time())
            hour, minute = now.hour, now.minute
            for (h, m) in SUMMARY_TIMES:
                if hour == h and minute == m and last_sent != (h, m):
                    with trade_log_lock:
                        logs = list(trade_log)
                    if logs:
                        df = pd.DataFrame(logs)
                        total_trades = len(df)
                        win_trades = (df['pnl_usdt'] > 0).sum()
                        lose_trades = total_trades - win_trades
                        avg_pnl_pct = df['pnl_pct'].mean()
                        total_pnl = df['pnl_usdt'].sum()
                        # Equity Curve
                        df['cumulative'] = df['pnl_usdt'].cumsum()
                        img_path = f"equity_{h}_{m}.png"
                        plt.figure()
                        plt.plot(df['cumulative'])
                        plt.title('Equity Curve')
                        plt.xlabel('Trade Index')
                        plt.ylabel('Cumulative PnL (USDT)')
                        plt.savefig(img_path)
                        plt.close()
                        msg = (
                            f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\n"
                            f"▶ Total Trades: {total_trades}\n"
                            f"▶ Wins: {win_trades}\n"
                            f"▶ Losses: {lose_trades}\n"
                            f"▶ Avg PnL %: {avg_pnl_pct:.2f}\n"
                            f"▶ Total PnL: {total_pnl:.2f} USDT"
                        )
                        send_telegram(msg)
                        send_telegram_photo(img_path)
                    else:
                        send_telegram(f"<b>🕒 Trade Summary {h:02d}:{m:02d}</b>\nNo trades recorded.")
                    last_sent = (h, m)
            time.sleep(30)
        except Exception as e:
            logging.error(f"[Trade Summary 오류] {e}")
            time.sleep(30)
