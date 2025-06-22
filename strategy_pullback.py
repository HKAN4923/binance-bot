"""Donchian based pullback strategy."""

from __future__ import annotations

import random


class StrategyPullback:
    """Simplified pullback strategy."""

    name = "PULLBACK"

    def check_entry(self):
        if random.random() < 0.1:
            side = random.choice(["LONG", "SHORT"])
            return {"symbol": "XRPUSDT", "side": side, "entry_price": 10.0}
        return None
