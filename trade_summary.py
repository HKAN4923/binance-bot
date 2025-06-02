import threading
import time
import logging
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from utils import to_kst
from telegram_notifier import send_telegram, send_telegram_photo
from config import SUMMARY_TIMES

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
                        
                        # 승/패 계산
                        win_trades = (df['pnl_pct'] > 0).sum()
                        lose_trades = total_trades - win_trades
                        
                        # 평균 수익률
                        avg_pnl = df['pnl_pct'].mean()
                        
                        # 총 수익
                        total_pnl_usdt = df['pnl_usdt'].sum()
                        
                        # 손익비 계산 (핵심 지표 추가)
                        avg_win = df[df['pnl_pct'] > 0]['pnl_pct'].mean()
                        avg_loss = df[df['pnl_pct'] < 0]['pnl_pct'].mean()
                        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
                        
                        # 청산 유형별 통계
                        exit_types = df['exit_type'].value_counts()
                        type_summary = "\n".join([f"▷ {typ}: {cnt}" for typ, cnt in exit_types.items()])
                        
                        # Equity Curve
                        df['cumulative_pnl'] = df['pnl_usdt'].cumsum()
                        plt.figure(figsize=(10, 6))
                        plt.plot(df['cumulative_pnl'])
                        plt.title('Equity Curve')
                        plt.xlabel('Trade Index')
                        plt.ylabel('Cumulative PnL (USDT)')
                        plt.grid(True)
                        
                        # 추가: 분포도 시각화
                        plt.figure(figsize=(10, 6))
                        plt.hist(df['pnl_pct'], bins=20, alpha=0.7)
                        plt.title('PnL Distribution')
                        plt.xlabel('PnL %')
                        plt.ylabel('Frequency')
                        
                        img_path = f"/tmp/equity_curve_{h}_{m}.png"
                        plt.savefig(img_path)
                        plt.close()
                        
                        msg = (
                            f"<b>📊 Trade Summary {h:02d}:{m:02d}</b>\n"
                            f"▶ 총 거래: {total_trades}\n"
                            f"▶ 승리: {win_trades} | 패배: {lose_trades}\n"
                            f"▶ 승률: {win_trades/total_trades*100:.1f}%\n"
                            f"▶ 평균 수익률: {avg_pnl:.2f}%\n"
                            f"▶ 손익비: {profit_factor:.2f}:1\n"
                            f"▶ 총 수익: {total_pnl_usdt:.2f} USDT\n\n"
                            f"<b>▷ 청산 유형</b>\n{type_summary}"
                        )
                        send_telegram(msg)
                        send_telegram_photo(img_path, caption="📈 자산 추이 및 분포")
                    else:
                        msg = f"<b>📊 Trade Summary {h:02d}:{m:02d}</b>\n이 기간 동안 거래 없음"
                        send_telegram(msg)
                    
                    last_sent = (h, m)
            time.sleep(30)
        except Exception as e:
            logging.error(f"Error in summary scheduler: {e}")
            time.sleep(30)
