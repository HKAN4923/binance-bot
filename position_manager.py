# position_manager.py - 현재 보유 포지션 관리

positions = {}

def add_position(symbol, side, entry_price, qty, strategy):
    positions[symbol] = {
        "side": side,
        "entry_price": entry_price,
        "qty": qty,
        "strategy": strategy,
    }

def remove_position(symbol):
    if symbol in positions:
        del positions[symbol]

def get_open_positions():
    return positions
