"""NR7 breakout strategy."""

from __future__ import annotations

import random
from datetime import datetime, timedelta


class StrategyNR7:
    """Simplified NR7 strategy implementation."""

    name = "NR7"

    def __init__(self) -> None:
        self.entered = False
        self.start_time = datetime.utcnow()

    def check_entry(self):
        if self.entered:
            return None
        if datetime.utcnow() - self.start_time > timedelta(hours=1):
            return None
        if random.random() < 0.1:
            self.entered = True
            side = random.choice(["LONG", "SHORT"])
            return {"symbol": "ETHUSDT", "side": side, "entry_price": 50.0}
        return None
