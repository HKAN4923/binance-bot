"""자동매매 봇 메인 실행 파일 (라쉬케5 구조 개선)
 - 모든 전략이 5초마다 전체 심볼 동시 탐색
 - EMA 조건 완화, Pullback 제거, Holy Grail 유지
"""

import logging
import time

import config
import order_manager
import position_manager
import trade_summary
import telegram_bot
from strategy_orb import StrategyORB
from strategy_nr7 import StrategyNR7
from strategy_ema_cross import StrategyEMACross
from strategy_holy_grail import StrategyHolyGrail
from risk_config import MAX_POSITIONS
from trade_summary import start_daily_file_sender

start_daily_file_sender()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/main.log"),
        logging.StreamHandler()
    ]
)

SYMBOL_LIST = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "MATICUSDT", "LTCUSDT", "TRXUSDT", "NEARUSDT", "UNIUSDT", "ATOMUSDT", "ETCUSDT", "ICPUSDT",
    "FILUSDT", "XLMUSDT", "SANDUSDT", "EGLDUSDT", "APEUSDT", "AAVEUSDT", "DYDXUSDT", "RUNEUSDT", "FTMUSDT",
    "INJUSDT", "GMXUSDT", "SNXUSDT", "ARBUSDT", "GRTUSDT", "CHZUSDT", "BLURUSDT", "CFXUSDT", "TWTUSDT",
    "ENSUSDT", "BANDUSDT", "FLOWUSDT", "ROSEUSDT", "CRVUSDT", "1INCHUSDT", "ZILUSDT", "KAVAUSDT", "STMXUSDT",
    "WAVESUSDT", "BCHUSDT", "ZRXUSDT", "MINAUSDT", "LINAUSDT"
]

def load_enabled_strategies():
    strategies = []
    if config.ORB_ENABLED:
        strategies.append(StrategyORB(SYMBOL_LIST))
    if config.NR7_ENABLED:
        strategies.append(StrategyNR7(SYMBOL_LIST))
    if config.EMA_ENABLED:
        strategies.append(StrategyEMACross(SYMBOL_LIST))
    if config.HOLY_GRAIL_ENABLED:
        strategies.append(StrategyHolyGrail(SYMBOL_LIST))
    return strategies

def print_analysis_status_loop():
    positions = position_manager.get_positions()
    count = len(positions)
    print(f"📡 실시간 분석중...({count}/{MAX_POSITIONS})")

def main_loop():
    telegram_bot.send_message("🚀 자동매매 봇이 시작되었습니다.")
    strategies = load_enabled_strategies()
    trade_summary.start_summary_scheduler()

    while True:
        try:
            for strat in strategies:
                for symbol in SYMBOL_LIST:
                    if not position_manager.can_enter(strat.name):
                        continue
                    signal = strat.check_entry(symbol)
                    if signal:
                        if position_manager.is_duplicate(signal["symbol"], strat.name):
                            continue
                        if position_manager.is_in_cooldown(signal["symbol"], strat.name):
                            continue
                        order_manager.place_entry_order(
                            signal["symbol"], signal["side"], strat.name
                        )

            order_manager.monitor_positions(strategies)  # ✅ 인자 추가됨
            print_analysis_status_loop()
            time.sleep(5)

        except Exception as e:
            logging.error(f"[오류] 메인 루프 중단됨: {e}")
            time.sleep(10)

import json
from pathlib import Path

def clear_json_files():
    for filename in ["trades.json", "positions.json"]:
        path = Path(filename)
        if path.exists():
            path.write_text("[]")

if __name__ == "__main__":

    main_loop()
