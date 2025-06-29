import time
import logging
from strategy_orb import ORBStrategy
from strategy_nr7 import NR7Strategy
from strategy_ema_cross import EMACrossStrategy
from strategy_holy_grail import HolyGrailStrategy
from order_manager import place_entry_order, monitor_positions
from position_manager import can_enter, is_duplicate, is_in_cooldown
from price_ws import start_price_websocket
from static_symbols import SYMBOLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

strategies = [
    ORBStrategy(),
    NR7Strategy(),
    EMACrossStrategy(),
    HolyGrailStrategy(),
]

def main_loop():
    start_price_websocket()
    logging.info("[WebSocket] 실시간 가격 수신 시작됨")

    while True:
        try:
            monitor_positions()

            for symbol in SYMBOLS:
                for strat in strategies:
                    if not can_enter(strat.name):
                        continue

                    signal = strat.check_entry(symbol)
                    if signal:
                        if is_duplicate(signal["symbol"], strat.name):
                            continue
                        if is_in_cooldown(signal["symbol"], strat.name):
                            continue

                        side = signal["side"].upper()
                        if side == "LONG":
                            side = "BUY"
                        elif side == "SHORT":
                            side = "SELL"

                        place_entry_order(signal["symbol"], side, strat.name)

                time.sleep(1)  # 심볼별 분석 간격

        except Exception as e:
            logging.error(f"[메인 루프 오류] {e}")
        
        time.sleep(5)  # 루프 반복 간격

if __name__ == "__main__":
    main_loop()
