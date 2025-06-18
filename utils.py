# utils.py
import json
import os
from datetime import datetime
from binance_api import get_futures_balance, get_lot_size, get_price, get_lot_precision
from risk_config import POSITION_RATIO, LEVERAGE, MIN_NOTIONAL

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_trade(data):
    path = "trade_log.json"
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([data], f, indent=4)
    else:
        with open(path, "r") as f:
            logs = json.load(f)
        logs.append(data)
        with open(path, "w") as f:
            json.dump(logs, f, indent=4)

def extract_entry_price(response):
    try:
        return float(response["avgFillPrice"])
    except:
        try:
            return float(response["fills"][0]["price"])
        except:
            return None

def calculate_order_quantity(symbol):
    usdt_balance = get_futures_balance()
    if usdt_balance is None:
        return 0
    amount = usdt_balance * POSITION_RATIO * LEVERAGE
    price = get_price(symbol)
    if price is None:
        return 0

    qty = amount / price
    min_qty = get_lot_size(symbol)
    if min_qty is None or qty * price < MIN_NOTIONAL:
        return 0

    precision = get_lot_precision(symbol)
    qty = round(qty, precision)

    return max(qty, min_qty)

def get_price(symbol):
    from binance_api import get_price
    return get_price(symbol)

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    if side == "long":
        tp = entry_price * (1 + tp_percent / 100)
        sl = entry_price * (1 - sl_percent / 100)
    else:
        tp = entry_price * (1 - tp_percent / 100)
        sl = entry_price * (1 + sl_percent / 100)
    return round(tp, 4), round(sl, 4)

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))
    average_gain = sum(gains) / period if gains else 0
    average_loss = sum(losses) / period if losses else 0
    if average_loss == 0:
        return 100
    rs = average_gain / average_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def summarize_trades():
    # TODO: 추후 실제 누적 손익 계산용 로직 연결
    return "📊 누적 손익 요약 기능은 준비 중입니다."
