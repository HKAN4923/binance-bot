# utils.py
import os
import json
import csv
from datetime import datetime, timedelta
from risk_config import *
import math
import requests

# utils.py

from binance_api import get_balance, get_price
from risk_config import POSITION_RATIO, LEVERAGE

def calculate_order_quantity(symbol):
    balance = get_balance()
    usdt_to_use = balance * POSITION_RATIO * LEVERAGE
    price = get_price(symbol)
    qty = usdt_to_use / price
    return round(qty, 3)  # 종목별로 precision 조정 가능

def utc_to_kst(utc_dt):
    return utc_dt + timedelta(hours=9)

def now_string():
    return utc_to_kst(datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S')

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    if side == "long":
        tp = entry_price * (1 + tp_percent / 100)
        sl = entry_price * (1 - sl_percent / 100)
    else:  # short
        tp = entry_price * (1 - tp_percent / 100)
        sl = entry_price * (1 + sl_percent / 100)
    return round(tp, 4), round(sl, 4)

def log_trade(data: dict, file_path='trade_log.csv'):
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

def calculate_slippage(expected_price, actual_price):
    return round(abs(expected_price - actual_price) / expected_price * 100, 3)

# utils.py에 추가


def get_step_size(symbol):
    url = f"https://fapi.binance.com/fapi/v1/exchangeInfo"
    res = requests.get(url).json()
    for s in res['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    return step_size
    return 0.001  # fallback

def round_quantity(qty, step_size):
    precision = int(round(-math.log10(step_size)))
    return round(qty, precision)

def calculate_order_quantity(symbol):
    balance = get_balance()
    usdt_to_use = balance * POSITION_RATIO * LEVERAGE
    price = get_price(symbol)
    raw_qty = usdt_to_use / price
    step = get_step_size(symbol)
    return round_quantity(raw_qty, step)
