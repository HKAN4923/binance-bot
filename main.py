# main.py

import time
import logging
import threading
from config import SYMBOLS, ANALYSIS_INTERVAL_SEC, POSITION_CHECK_INTERVAL_SEC
from telegram_bot import send_message
from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from strategy_pullback import check_entry as pull_entry, check_exit as pull_exit
from trade_summary import start_summary_scheduler
from position_manager import get_positions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    handlers=[logging.StreamHandler()]
)

# 시작 알림
send_message("🤖 라쉬케4 자동매매 봇 시작됨")

# 전략 진입 스케줄러
def strategy_entry_loop():
    while True:
        for symbol in SYMBOLS:
            # ORB는 09:00~10:00, 21:00~22:00만
            orb_entry(symbol)

            # NR7은 1시간마다 돌파 체크 (09시 이후부터 가능)
            nr7_entry(symbol)

            # EMA/RSI 전략
            ema_entry(symbol)

            # Pullback (단타전략)
            pull_entry(symbol)

        time.sleep(ANALYSIS_INTERVAL_SEC)

# 전략 청산 스케줄러
def position_monitor_loop():
    while True:
        positions = get_positions()
        for pos in positions:
            symbol = pos["symbol"]
            strategy = pos["strategy"]

            if strategy == "ORB":
                orb_exit(symbol)
            elif strategy == "NR7":
                nr7_exit(symbol)
            elif strategy == "EMA":
                ema_exit(symbol)
            elif strategy == "Pullback":
                pull_exit(symbol)

        time.sleep(POSITION_CHECK_INTERVAL_SEC)

def main():
    # 청산 모니터 스레드 시작
    threading.Thread(target=position_monitor_loop, daemon=True).start()

    # 2시간마다 요약 전송 스레드 시작
    start_summary_scheduler()

    # 진입 전략 루프 시작 (메인 스레드)
    strategy_entry_loop()

if __name__ == "__main__":
    main()
