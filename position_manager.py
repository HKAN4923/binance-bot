# position_manager.py - 현재 보유 포지션 관리
from datetime import datetime
from risk_config import MAX_POSITIONS

positions = {}

def can_enter(symbol, strategy):
    return len(positions) < MAX_POSITIONS and symbol not in positions

def add_position(symbol, side, entry_price, qty, strategy):
    positions[symbol] = {
        "side": side,
        "entry_price": entry_price,
        "qty": qty,
        "strategy": strategy,
        "entry_time": datetime.utcnow()  # ✅ 전략별 시간 조건에 필요
    }

def remove_position(symbol):
    if symbol in positions:
        del positions[symbol]

def get_open_positions():
    return positions
