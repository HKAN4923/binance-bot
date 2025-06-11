# main.py
import time
from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pullback_entry, check_exit as pullback_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from position_manager import open_positions
from telegram_bot import send_telegram
from binance_api import get_price
from utils import now_string

SYMBOL_LIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]  # 기본 심볼 리스트

def run_all_entries():
    for symbol in SYMBOL_LIST:
        orb_entry(symbol)
        nr7_entry(symbol)
        pullback_entry(symbol)
        ema_entry(symbol)

def run_all_exits():
    for symbol in list(open_positions.keys()):
        orb_exit(symbol)
        nr7_exit(symbol)
        pullback_exit(symbol)
        ema_exit(symbol)

def report_summary():
    wins, losses, pnl = 0, 0, 0.0
    try:
        with open("trade_log.csv", "r") as f:
            lines = f.readlines()[1:]  # skip header
            for line in lines:
                row = line.strip().split(",")
                if row[5] == "exit":
                    entry = float(row[4])
                    exit_ = float(row[3])
                    profit = (exit_ - entry) if row[2] == "long" else (entry - exit_)
                    pnl += profit
                    if profit > 0:
                        wins += 1
                    else:
                        losses += 1
        total = wins + losses
        winrate = round((wins / total) * 100, 2) if total > 0 else 0
        send_telegram(f"📊 누적 통계\n진입 수: {total}\n승: {wins} / 패: {losses}\n승률: {winrate}%\n손익합계: {round(pnl,2)}$")
    except:
        pass

if __name__ == "__main__":
    send_telegram("🤖 봇 시작됨")

    loop_counter = 0
    while True:
        run_all_entries()

        print(f"[{now_string()}] 분석 중... (진입 포지션 수: {len(open_positions)} / 최대: {MAX_POSITION_COUNT})")

        run_all_exits()

        if loop_counter % 720 == 0:  # 10초마다 1회 → 720 = 2시간
            report_summary()

        time.sleep(10)
        loop_counter += 1
