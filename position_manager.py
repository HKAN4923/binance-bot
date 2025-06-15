from risk_config import MAX_POSITION_COUNT
open_positions = {}

def can_enter(symbol, strategy):
    return len(open_positions) < MAX_POSITION_COUNT and symbol not in open_positions

def add_position(symbol, entry_price, strategy, side, qty):
    from datetime import datetime
    if qty <= 0:
        print(f"[{symbol}] 체결 수량 없음 → 포지션 등록 생략")
        return
    open_positions[symbol] = {
        "entry_price": entry_price,
        "strategy": strategy,
        "side": side,
        "position_size": qty,
        "entry_time": datetime.utcnow()
    }

def remove_position(symbol):
    if symbol in open_positions:
        del open_positions[symbol]

def get_position(symbol):
    return open_positions.get(symbol)