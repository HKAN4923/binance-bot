from risk_config import LEVERAGE, POSITION_RATIO
import math
import time

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    tp = entry_price * (1 + tp_percent / 100) if side == "long" else entry_price * (1 - tp_percent / 100)
    sl = entry_price * (1 - sl_percent / 100) if side == "long" else entry_price * (1 + sl_percent / 100)
    return round(tp, 2), round(sl, 2)

def calculate_order_quantity(symbol):
    try:
        from binance_api import get_price
        price = get_price(symbol)
        if price is None: return 0
        balance = 50  # 실 계좌에서는 실제 잔고 가져오기
        qty = (balance * POSITION_RATIO * LEVERAGE) / price
        return round(qty, 3)
    except Exception as e:
        print(f"[ERROR] calculate_order_quantity: {e}")
        return 0

def extract_entry_price(order_resp):
    try:
        return float(order_resp["avgFillPrice"]) if "avgFillPrice" in order_resp else None
    except Exception as e:
        print(f"[ERROR] extract_entry_price: {e}")
        return None

def log_trade(data):
    try:
        with open("trades.log", "a") as f:
            f.write(str(data) + "\n")
    except Exception as e:
        print(f"[ERROR] log_trade: {e}")

def now_string():
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")