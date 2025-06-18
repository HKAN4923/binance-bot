# utils.py
import time
from datetime import datetime
from binance_api import get_futures_balance, get_price, get_lot_size
from risk_config import POSITION_RATIO, LEVERAGE, MIN_NOTIONAL

def now_string():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def calculate_tp_sl(entry_price, tp_percent, sl_percent, direction):
    if direction == "long":
        tp = entry_price * (1 + tp_percent / 100)
        sl = entry_price * (1 - sl_percent / 100)
    else:
        tp = entry_price * (1 - tp_percent / 100)
        sl = entry_price * (1 + sl_percent / 100)
    return round(tp, 4), round(sl, 4)

def log_trade(info: dict):
    print("🧾 TRADE LOG")
    for k, v in info.items():
        print(f"{k}: {v}")

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

def get_current_time_kst():
    return datetime.utcfromtimestamp(time.time() + 9 * 60 * 60)

def calculate_order_quantity(symbol):
    balance = get_futures_balance()
    price = get_price(symbol)
    lot_size = get_lot_size(symbol)
    
    if balance is None or price is None or lot_size is None:
        print(f"[{symbol}] 계산 불가: 잔고={balance}, 가격={price}, 로트={lot_size}")
        return 0

    order_value = balance * POSITION_RATIO * LEVERAGE
    qty = order_value / price

    # 최소 수량 기준 반영
    min_qty = lot_size["minQty"]
    step_size = lot_size["stepSize"]

    # step_size 반올림
    precision = abs(round(float(step_size)).as_integer_ratio()[1].bit_length() - 1)
    qty = max(min_qty, round(qty, precision))

    notional = qty * price
    if notional < MIN_NOTIONAL:
        print(f"[{symbol}] 금액 부족 → ${notional:.2f} < ${MIN_NOTIONAL}")
        return 0

    return qty

# 누적 요약 메시지
def summarize_trades():
    from trade_summary import get_trade_summary  # 순환참조 방지
    total, wins, losses, win_rate, total_pl = get_trade_summary()
    return f"📊 총 {total}회 | {wins}승 {losses}패 | 승률: {win_rate:.1f}%\n누적 손익: {total_pl:+.2f} USDT"
