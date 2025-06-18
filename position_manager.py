# position_manager.py - 현재 보유 포지션 관리
from datetime import datetime
from risk_config import MAX_POSITIONS

open_positions = {}  # ✅ 외부 import용 이름으로 정의

def can_enter(symbol, strategy):
    return len(open_positions) < MAX_POSITIONS and symbol not in open_positions

def add_position(symbol, side, entry_price, qty, strategy):
    open_positions[symbol] = {
        "side": side,
        "entry_price": entry_price,
        "qty": qty,
        "strategy": strategy,
        "entry_time": datetime.utcnow()
    }

def remove_position(symbol):
    if symbol in open_positions:
        del open_positions[symbol]

def get_open_positions():
    return open_positions

def get_position(symbol):
    return open_positions.get(symbol)
