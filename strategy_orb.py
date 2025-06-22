"""Opening Range Breakout strategy."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

import utils


class StrategyORB:
    """Simplified ORB strategy implementation."""

    name = "ORB"

    def __init__(self) -> None:
        self.entered = False
        self.start_time = datetime.utcnow()

    def check_entry(self):
        """Return an entry signal if conditions are met."""
        if self.entered:
            return None
        # allow entry only within first hour
        if datetime.utcnow() - self.start_time > timedelta(hours=1):
            return None
        if random.random() < 0.1:  # pseudo condition
            self.entered = True
            side = random.choice(["LONG", "SHORT"])
            return {"symbol": "BTCUSDT", "side": side, "entry_price": 100.0}
        return None