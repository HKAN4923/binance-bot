import time
import logging

from config import ORB_ENABLED, NR7_ENABLED, EMA_ENABLED, HOLY_GRAIL_ENABLED
from strategy_orb import StrategyORB
from strategy_nr7 import StrategyNR7
from strategy_ema_cross import StrategyEMACross
from strategy_holy_grail import StrategyHolyGrail

from order_manager import place_entry_order, monitor_positions
from position_manager import can_enter, is_duplicate, is_in_cooldown, get_positions
from price_ws import start_price_ws
from trade_summary import start_summary_scheduler, start_daily_file_sender

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

SYMBOL_LIST = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "MATICUSDT", "LTCUSDT", "TRXUSDT", "NEARUSDT", "UNIUSDT", "ATOMUSDT", "ETCUSDT", "ICPUSDT",
    "FILUSDT", "XLMUSDT", "SANDUSDT", "EGLDUSDT", "APEUSDT", "AAVEUSDT", "DYDXUSDT", "RUNEUSDT", "FTMUSDT",
    "INJUSDT", "GMXUSDT", "SNXUSDT", "ARBUSDT", "GRTUSDT", "CHZUSDT", "BLURUSDT", "CFXUSDT", "TWTUSDT",
    "ENSUSDT", "BANDUSDT", "FLOWUSDT", "ROSEUSDT", "CRVUSDT", "1INCHUSDT", "ZILUSDT", "KAVAUSDT", "STMXUSDT",
    "WAVESUSDT", "BCHUSDT", "ZRXUSDT", "MINAUSDT", "LINAUSDT"
]

strategies = []
if ORB_ENABLED:
    strategies.append(StrategyORB(SYMBOL_LIST))
if NR7_ENABLED:
    strategies.append(StrategyNR7(SYMBOL_LIST))
if EMA_ENABLED:
    strategies.append(StrategyEMACross(SYMBOL_LIST))
if HOLY_GRAIL_ENABLED:
    strategies.append(StrategyHolyGrail(SYMBOL_LIST))

def main_loop():
    start_price_ws(SYMBOL_LIST)
    start_summary_scheduler()
    start_daily_file_sender()
    logging.info("[봇 시작] 실시간 WebSocket 수신, 요약 전송 스케줄러 시작됨")

    while True:
        try:
            monitor_positions()

            open_positions = get_positions()
            logging.info(f"[분석중... ({len(open_positions)}/4)]")

            for symbol in SYMBOL_LIST:
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

                time.sleep(0.5)

        except Exception as e:
            logging.error(f"[메인 루프 오류] {e}")


if __name__ == "__main__":
    main_loop()
