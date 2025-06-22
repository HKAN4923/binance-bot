"""Utility functions for calculations used across the trading bot."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

from zoneinfo import ZoneInfo


def calculate_order_quantity(symbol: str, price: float, balance: float = 1000) -> float:
    """Return order quantity based on balance and risk configuration."""
    from risk_config import CAPITAL_USAGE, LEVERAGE

    qty = balance * CAPITAL_USAGE * LEVERAGE / price
    return round_quantity(symbol, qty)


def calculate_rsi(prices: Iterable[float], period: int = 14) -> float:
    """Calculate the Relative Strength Index (RSI)."""
    prices = list(prices)
    if len(prices) < period + 1:
        raise ValueError("Not enough data for RSI calculation")

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        delta = prices[-i] - prices[-i - 1]
        if delta >= 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period if losses else 0.0

    if average_loss == 0:
        return 100.0

    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


def to_kst(dt: datetime) -> datetime:
    """Convert a UTC datetime to Korea Standard Time."""
    return dt.astimezone(ZoneInfo("Asia/Seoul"))


def apply_slippage(price: float, side: str, rate: float) -> float:
    """Apply slippage to the given price depending on side."""
    if side.upper() == "LONG":
        return price * (1 + rate)
    return price * (1 - rate)


def round_price(symbol: str, price: float, tick_size: float = 0.01) -> float:
    """Round a price down using the tick size."""
    return math.floor(price / tick_size) * tick_size


def round_quantity(symbol: str, qty: float, step_size: float = 0.001) -> float:
    """Round a quantity down using the step size."""
    return math.floor(qty / step_size) * step_size
