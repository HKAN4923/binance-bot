"Order placement and monitoring logic."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import utils
from position_manager import add_position, remove_position


POSITIONS_TO_MONITOR: List[Dict[str, Any]] = []


def place_entry_order(symbol: str, side: str, strategy_name: str) -> Dict[str, Any]:
    """Simulate a market entry order and register the position."""
    entry_price = 100.0  # placeholder
    qty = utils.calculate_order_quantity(symbol, entry_price)
    position = {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "strategy": strategy_name,
        "entry_time": datetime.utcnow().isoformat(),
    }
    logging.info("Entering %s %s via %s", symbol, side, strategy_name)
    add_position(position)
    POSITIONS_TO_MONITOR.append(position)
    return position


def get_sl_tp_price(price: float, side: str) -> tuple[float, float]:
    """Calculate stop-loss and take-profit prices."""
    if side.upper() == "LONG":
        tp = price * 1.02
        sl = price * 0.99
    else:
        tp = price * 0.98
        sl = price * 1.01
    return tp, sl


def place_tp_sl_orders(symbol: str, side: str, entry_price: float) -> None:
    """Placeholder for placing TP/SL orders."""
    tp, sl = get_sl_tp_price(entry_price, side)
    logging.info("Placed TP %.2f and SL %.2f for %s", tp, sl, symbol)


def monitor_positions() -> None:
    """Monitor positions and exit when TP or SL hit (simulated)."""
    closed = []
    for pos in POSITIONS_TO_MONITOR:
        # In a real bot, current price would be fetched from the exchange
        current_price = pos["entry_price"]
        tp, sl = get_sl_tp_price(pos["entry_price"], pos["side"])
        if pos["side"] == "LONG" and current_price >= tp:
            logging.info("%s hit take profit", pos["symbol"])
            closed.append(pos)
        elif pos["side"] == "LONG" and current_price <= sl:
            logging.info("%s hit stop loss", pos["symbol"])
            closed.append(pos)
        elif pos["side"] == "SHORT" and current_price <= tp:
            logging.info("%s hit take profit", pos["symbol"])
            closed.append(pos)
        elif pos["side"] == "SHORT" and current_price >= sl:
            logging.info("%s hit stop loss", pos["symbol"])
            closed.append(pos)

    for pos in closed:
        POSITIONS_TO_MONITOR.remove(pos)
        remove_position(pos)


def force_market_exit(position: Dict[str, Any]) -> None:
    """Forcefully exit a position (simulated)."""
    if position in POSITIONS_TO_MONITOR:
        POSITIONS_TO_MONITOR.remove(position)
    remove_position(position)
    logging.info("Force exited position %s", position["symbol"])