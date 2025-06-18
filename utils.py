import time
from datetime import datetime,timedelta
from binance_api import get_symbol_min_qty


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def apply_slippage(price, side, slippage_pct=0.001):
    if side == "BUY":
        return round(price * (1 + slippage_pct), 2)
    else:
        return round(price * (1 - slippage_pct), 2)

def calculate_quantity(usdt_balance, price, leverage, symbol):
    try:
        notional = usdt_balance * leverage
        qty = notional / price
        min_qty = get_symbol_min_qty(symbol)
        if min_qty is None or qty < float(min_qty):
            return 0
        precision = len(min_qty.split('.')[-1])
        return round(qty, precision)
    except Exception as e:
        print(f"[수량 계산 오류] {symbol}: {e}")
        return 0

def calculate_tp_sl(entry_price, side, rr_ratio=2.0, sl_pct=0.01):
    if side == "BUY":
        stop_loss = round(entry_price * (1 - sl_pct), 2)
        take_profit = round(entry_price * (1 + sl_pct * rr_ratio), 2)
    else:
        stop_loss = round(entry_price * (1 + sl_pct), 2)
        take_profit = round(entry_price * (1 - sl_pct * rr_ratio), 2)
    return take_profit, stop_loss

def to_kst(timestamp):
    """UTC timestamp → KST datetime"""
    return datetime.utcfromtimestamp(timestamp) + timedelta(hours=9)