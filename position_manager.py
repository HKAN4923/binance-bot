# ✅ position_manager.py
import time
from datetime import datetime, timedelta
from risk_config import MAX_POSITION_COUNT

open_positions = {}  # { symbol: { entry_price, entry_time, strategy, side, position_size } }
recent_entries = {}  # { (symbol, strategy): last_entry_time }

def can_enter(symbol, strategy):
    now = datetime.utcnow()
    if len(open_positions) >= MAX_POSITION_COUNT:
        return False
    key = (symbol, strategy)
    if key in recent_entries:
        timeout_minutes = {
            "pullback": 60,
            "ema": 60,
        }.get(strategy, 0)
        if timeout_minutes > 0 and now - recent_entries[key] < timedelta(minutes=timeout_minutes):
            return False
    return True

def add_position(symbol, entry_price, strategy, side, qty):
    now = datetime.utcnow()
    open_positions[symbol] = {
        "entry_price": entry_price,
        "entry_time": now,
        "strategy": strategy,
        "side": side,
        "position_size": qty
    }
    recent_entries[(symbol, strategy)] = now

def remove_position(symbol):
    if symbol in open_positions:
        del open_positions[symbol]
