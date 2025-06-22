"""EMA cross strategy with RSI filter."""

from __future__ import annotations

import random


class StrategyEMACross:
    """Simplified EMA cross strategy."""

    name = "EMA"

    def check_entry(self):
        if random.random() < 0.1:
            side = random.choice(["LONG", "SHORT"])
            return {"symbol": "BNBUSDT", "side": side, "entry_price": 30.0}
        return None