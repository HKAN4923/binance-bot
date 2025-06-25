"""자동매매 봇 메인 실행 파일"""

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
from strategy_pullback import StrategyPullback
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


def load_enabled_strategies():
    """활성화된 전략 목록 반환"""
    strategies = []
    if config.ORB_ENABLED:
        strategies.append(StrategyORB())
    if config.NR7_ENABLED:
        strategies.append(StrategyNR7())
    if config.EMA_ENABLED:
        strategies.append(StrategyEMACross())
    if config.PULLBACK_ENABLED:
        strategies.append(StrategyPullback())
    return strategies


def print_analysis_status_loop():
    positions = position_manager.get_positions()
    count = len(positions)
    print(f"📡 실시간 분석중...({count}/{MAX_POSITIONS})")

def main_loop():
    """자동매매 루프 시작"""
    telegram_bot.send_message("🚀 자동매매 봇이 시작되었습니다.")

    strategies = load_enabled_strategies()
    trade_summary.start_summary_scheduler()

    while True:
        try:
            for strat in strategies:
                if not position_manager.can_enter(strat.name):
                    continue
                signal = strat.check_entry()
                if signal:
                    if position_manager.is_duplicate(signal["symbol"], strat.name):
                        continue
                    if position_manager.is_in_cooldown(signal["symbol"], strat.name):
                        continue
                    order_manager.place_entry_order(
                        signal["symbol"], signal["side"], strat.name
                    )
                    

            order_manager.monitor_positions()
            print_analysis_status_loop()
            time.sleep(10)

        except Exception as e:
            logging.error(f"[오류] 메인 루프 중단됨: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main_loop()
