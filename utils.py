import math
from binance_api import get_price, get_futures_balance, get_lot_size
from risk_config import POSITION_RATIO, LEVERAGE

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    tp = entry_price * (1 + tp_percent / 100) if side == "long" else entry_price * (1 - tp_percent / 100)
    sl = entry_price * (1 - sl_percent / 100) if side == "long" else entry_price * (1 + sl_percent / 100)
    return round(tp, 2), round(sl, 2)

def calculate_order_quantity(symbol):
    try:
        price = get_price(symbol)
        if price is None or price == 0:
            print(f"[{symbol}] 가격 조회 실패")
            return 0

        balance = get_futures_balance()
        base_value = balance * POSITION_RATIO
        order_value = base_value * LEVERAGE
        qty = order_value / price

        step_size = get_lot_size(symbol)
        if step_size is None:
            print(f"[{symbol}] 최소 수량 정보 없음")
            return 0

        precision = abs(int(round(-1 * math.log10(step_size))))
        final_qty = round(qty, precision)
        notional = final_qty * price

        if final_qty < step_size:
            print(f"[{symbol}] 수량 부족 → {final_qty} < {step_size}")
            return 0

        if notional < 20:
            print(f"[{symbol}] 금액 부족 → ${notional:.2f} < $20")
            return 0

        return final_qty
    except Exception as e:
        print(f"[{symbol}] 수량 계산 오류: {e}")
        return 0

def extract_entry_price(order_resp):
    try:
        if not order_resp:
            print("[주문 실패] 응답 없음")
            return None
        if float(order_resp.get("executedQty", 0)) == 0:
            print("[주문 실패] 체결되지 않음 (executedQty = 0)")
            return None
        return float(order_resp.get("avgFillPrice", 0))
    except Exception as e:
        print(f"[extract_entry_price 오류] {e}")
        return None

def log_trade(data):
    try:
        assert "tp" in data and "sl" in data, "[오류] TP/SL 누락됨"
        with open("trades.log", "a") as f:
            f.write(str(data) + "\n")
    except AssertionError as ae:
        print(f"[로그 저장 오류] {ae}")
    except Exception as e:
        print(f"[로그 저장 오류] {e}")

def now_string():
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")