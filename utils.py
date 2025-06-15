from binance_api import get_price, get_futures_balance
from risk_config import POSITION_RATIO

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    tp = entry_price * (1 + tp_percent / 100) if side == "long" else entry_price * (1 - tp_percent / 100)
    sl = entry_price * (1 - sl_percent / 100) if side == "long" else entry_price * (1 + sl_percent / 100)
    return round(tp, 2), round(sl, 2)

def calculate_order_quantity(symbol):
    try:
        price = get_price(symbol)
        if price is None or price == 0:
            print(f"[ERROR] {symbol} 가격 조회 실패 또는 0")
            return 0

        balance = get_futures_balance()
        order_value = balance * POSITION_RATIO  # 레버리지 1배
        qty = order_value / price

        # 최소 주문 수량 (코인별)
        MIN_QTY = {
            "BTCUSDT": 0.001,
            "ETHUSDT": 0.01,
        }
        min_qty = MIN_QTY.get(symbol, 0.001)

        final_qty = round(qty, 3)
        if final_qty < min_qty:
            print(f"[SKIP] {symbol} 주문 수량({final_qty})이 최소 수량({min_qty})보다 작음")
            return 0

        return final_qty
    except Exception as e:
        print(f"[ERROR] calculate_order_quantity: {e}")
        return 0

def extract_entry_price(order_resp):
    try:
        if not order_resp or "avgFillPrice" not in order_resp:
            return None
        return float(order_resp["avgFillPrice"])
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