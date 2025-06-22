"Manage open positions for the trading bot."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import utils
from risk_config import COOLDOWN_MINUTES, MAX_POSITIONS, RESERVED_SLOTS


POSITIONS_FILE = Path("positions.json")

# In-memory cache of positions
_positions: List[Dict[str, Any]] | None = None


def _load_positions() -> List[Dict[str, Any]]:
    global _positions
    if _positions is None:
        if POSITIONS_FILE.exists():
            _positions = json.loads(POSITIONS_FILE.read_text())
        else:
            _positions = []
    return _positions


def _save() -> None:
    if _positions is not None:
        POSITIONS_FILE.write_text(json.dumps(_positions, indent=2))


def get_positions() -> List[Dict[str, Any]]:
    """Return current positions."""
    return list(_load_positions())


def can_enter(strategy_name: str) -> bool:
    """Return True if a new position can be opened for given strategy."""
    positions = _load_positions()
    if len(positions) >= MAX_POSITIONS:
        return False

    if strategy_name.upper() in {"ORB", "NR7"}:
        # reserved slots for ORB/NR7 strategies
        non_reserved = [p for p in positions if p["strategy"] not in {"ORB", "NR7"}]
        if len(non_reserved) >= MAX_POSITIONS - RESERVED_SLOTS:
            return False
    return True


def add_position(position: Dict[str, Any]) -> None:
    """Add a position to the list and persist."""
    positions = _load_positions()
    positions.append(position)
    _save()


def remove_position(position: Dict[str, Any]) -> None:
    """Remove a position from storage."""
    positions = _load_positions()
    try:
        positions.remove(position)
        _save()
    except ValueError:
        pass


def is_duplicate(symbol: str, strategy_name: str) -> bool:
    """Check if the symbol is already traded by the same strategy."""
    for pos in _load_positions():
        if pos["symbol"] == symbol and pos["strategy"] == strategy_name:
            return True
    return False


def is_in_cooldown(symbol: str, strategy_name: str) -> bool:
    """Check if a position is in cooldown period."""
    now = datetime.utcnow()
    for pos in _load_positions():
        if (
            pos["symbol"] == symbol
            and pos["strategy"] == strategy_name
            and now - datetime.fromisoformat(pos["entry_time"]) < timedelta(minutes=COOLDOWN_MINUTES)
        ):
            return True
    return False
