# 파일명: main.py
# 메인 실행 스크립트
# core.py와 전략 모듈을 활용해 시장 분석 → 진입/청산 처리 → 텔레그램 알림 등을 수행합니다.

import threading
import time
import logging

from core import (
    get_filtered_top_symbols,
    get_open_positions,
    get_position,
    send_telegram
)
from config import MAX_POSITIONS, ANALYSIS_INTERVAL_SEC
from trade_summary import start_summary_scheduler
from position_monitor import PositionMonitor
from order_manager import cancel_all_orders_for_symbol

from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pb_entry, check_exit as pb_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit

# 잔재 주문 정리
def cleanup_orphan_orders():
    while True:
        try:
            tracked = set(get_open_positions().keys())
            open_orders = client.futures_get_open_orders()  # client는 binance_client.py에서 글로벌
            for o in open_orders:
                sym = o['symbol']
                if sym not in tracked:
                    cancel_all_orders_for_symbol(sym)
            time.sleep(10)
        except Exception as e:
            logging.error(f"cleanup_orphan_orders 오류: {e}")
            time.sleep(10)

# 시장 분석 및 전략 실행
def analyze_market():
    # 심볼 풀 로드 (오류 심볼 사전 필터링)
    symbols = get_filtered_top_symbols(100)
    while True:
        try:
            current_positions = len(get_open_positions())
            logging.info(f"분석중... ({current_positions}/{MAX_POSITIONS})")
            # 진입 조건 체크
            for sym in symbols:
                if len(get_open_positions()) >= MAX_POSITIONS:
                    break
                orb_entry(sym)
                nr7_entry(sym)
                pb_entry(sym)
                ema_entry(sym)

            # 청산 조건 체크
            for sym in list(get_open_positions().keys()):
                orb_exit(sym)
                nr7_exit(sym)
                pb_exit(sym)
                ema_exit(sym)

            time.sleep(ANALYSIS_INTERVAL_SEC)
        except Exception as e:
            logging.error(f"analyze_market 오류: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    try:
        send_telegram("<b>🤖 봇 시작</b>")
    except:
        pass

    # 요약 스케줄러 시작
    start_summary_scheduler()

    # 포지션 모니터링 스레드
    pos_mon = PositionMonitor()
    pos_mon.start()

    # 주문 정리 및 시장 분석 스레드
    threading.Thread(target=cleanup_orphan_orders, daemon=True).start()
    threading.Thread(target=analyze_market, daemon=True).start()

    # 메인 루프
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        pos_mon.stop()
        logging.info("봇 종료")
        exit(0)
