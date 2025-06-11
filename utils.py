# utils.py
import os
import json
import csv
from datetime import datetime, timedelta
from risk_config import *

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
