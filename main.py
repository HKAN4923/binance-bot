"""Entry point for running the trading bot."""

from __future__ import annotations

import asyncio
import logging
from typing import List

import config
import order_manager
import position_manager
import trade_summary
from strategy_ema_cross import StrategyEMACross
from strategy_nr7 import StrategyNR7
from strategy_orb import StrategyORB
from strategy_pullback import StrategyPullback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


class Bot:
    """Main trading bot class."""

    def __init__(self) -> None:
        self.strategies = self.load_enabled_strategies()
        self.counter = 0
        trade_summary.start_summary_scheduler()

    def load_enabled_strategies(self) -> List[Any]:
        """Load strategy instances based on config."""
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

    async def run_entry_loop(self) -> None:
        """Periodically check strategies for entry signals."""
        while True:
            for strat in self.strategies:
                signal = strat.check_entry()
                if signal and position_manager.can_enter(strat.name):
                    order_manager.place_entry_order(
                        signal["symbol"], signal["side"], strat.name
                    )
                    order_manager.place_tp_sl_orders(
                        signal["symbol"], signal["side"], signal["entry_price"]
                    )
            await asyncio.sleep(10)

    async def run_monitoring_loop(self) -> None:
        """Monitor open positions."""
        while True:
            order_manager.monitor_positions()
            await asyncio.sleep(5)

    async def print_analysis_status(self) -> None:
        """Print a status line every 10 seconds."""
        max_val = len(self.strategies)
        while True:
            self.counter = (self.counter + 1) % (max_val + 1)
            logging.info("Analyzing... (%d/%d)", self.counter, max_val)
            await asyncio.sleep(10)

    def run(self) -> None:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.create_task(self.run_entry_loop()),
            loop.create_task(self.run_monitoring_loop()),
            loop.create_task(self.print_analysis_status()),
        ]
        try:
            loop.run_until_complete(asyncio.gather(*tasks))
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")


if __name__ == "__main__":
    Bot().run()
