# File: main.py
import time
from binance_client import BinanceClient
from strategy import ATRBreakoutStrategy
from risk_manager import RiskManager
from notifier import TelegramNotifier
from position_monitor import PositionMonitor
from sltp_cleaner import SLTPCleaner
from config import Config


def main():
    client = BinanceClient()
    strat = ATRBreakoutStrategy(client)
    risk = RiskManager(client)
    monitor = PositionMonitor(client)
    cleaner = SLTPCleaner(client)
    cleaner.start()

    symbols = client.client.futures_exchange_info()["symbols"]
    # filter top 100 by volume or load from config
    selected = [s['symbol'] for s in symbols][:100]
    entered_today = 0

    while True:
        for sym in selected:
            monitor.check_drawdown()
            if entered_today >= Config.ENTRY_TARGET_PER_DAY:
                break
            positions = client.client.futures_position_information(symbol=sym)
            open_positions = [p for p in positions if float(p['positionAmt']) != 0]
            if not risk.can_enter(len(open_positions)):
                continue
            signal = strat.generate_signals(sym)
            if signal:
                qty = risk.position_size(signal['price'])
                order = client.place_order(sym, signal['side'], qty, stop_loss=signal['sl'], take_profit=signal['tp'])
                TelegramNotifier.notify(f"{sym} {signal['side']} @ {signal['price']}, SL {signal['sl']}, TP {signal['tp']}")
                entered_today += 1
        time.sleep(60)  # wait before next cycle

if __name__ == "__main__":
    main()
