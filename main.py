import time
import logging

from strategy_orb import StrategyORB
from strategy_nr7 import StrategyNR7
from strategy_ema_cross import StrategyEMACross
from strategy_holy_grail import StrategyHolyGrail

from order_manager import place_entry_order, monitor_positions
from position_manager import can_enter, is_duplicate, is_in_cooldown, get_positions
from price_ws import start_price_ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

SYMBOL_LIST = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "MATICUSDT", "LTCUSDT", "TRXUSDT", "NEARUSDT", "UNIUSDT", "ATOMUSDT", "ETCUSDT", "ICPUSDT",
    "FILUSDT", "XLMUSDT", "SANDUSDT", "EGLDUSDT", "APEUSDT", "AAVEUSDT", "DYDXUSDT", "RUNEUSDT", "FTMUSDT",
    "INJUSDT", "GMXUSDT", "SNXUSDT", "ARBUSDT", "GRTUSDT", "CHZUSDT", "BLURUSDT", "CFXUSDT", "TWTUSDT",
    "ENSUSDT", "BANDUSDT", "FLOWUSDT", "ROSEUSDT", "CRVUSDT", "1INCHUSDT", "ZILUSDT", "KAVAUSDT", "STMXUSDT",
    "WAVESUSDT", "BCHUSDT", "ZRXUSDT", "MINAUSDT", "LINAUSDT"
]

strategies = [
    StrategyORB(SYMBOL_LIST),
    StrategyNR7(SYMBOL_LIST),
    StrategyEMACross(SYMBOL_LIST),
    StrategyHolyGrail(SYMBOL_LIST),
]

def main_loop():
    start_price_ws(SYMBOL_LIST)
    logging.info("[WebSocket] 실시간 가격 수신 시작됨")

    while True:
        try:
            monitor_positions()

            open_positions = get_positions()
            logging.info(f"[분석중... ({len(open_positions)}/4)]")

            for symbol in SYMBOL_LIST:
                for strat in strategies:
                    if not can_enter(strat.name):
                        logging.debug(f"[{strat.name}] {symbol} → 슬롯 초과로 스킵")
                        continue

                    signal = strat.check_entry(symbol)
                    if signal:
                        logging.info(f"[{strat.name}] {symbol} 진입 조건 충족 → {signal['side'].upper()}")
                        if is_duplicate(signal["symbol"], strat.name):
                            logging.debug(f"[{strat.name}] {symbol} 중복 진입 방지")
                            continue
                        if is_in_cooldown(signal["symbol"], strat.name):
                            logging.debug(f"[{strat.name}] {symbol} 쿨타임 중으로 스킵")
                            continue

                        side = signal["side"].upper()
                        if side == "LONG":
                            side = "BUY"
                        elif side == "SHORT":
                            side = "SELL"

                        place_entry_order(signal["symbol"], side, strat.name)
                    else:
                        logging.debug(f"[{strat.name}] {symbol} 조건 미충족")

                time.sleep(0.5)  # 전략별 분석 간격

        except Exception as e:
            logging.error(f"[메인 루프 오류] {e}")



if __name__ == "__main__":
    main_loop()
