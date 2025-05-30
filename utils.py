import time
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

def to_kst(ts=None):
    return datetime.fromtimestamp(ts or time.time(), KST).strftime("%H:%M:%S")

def calculate_qty(balance, price, leverage, fraction, qty_precision):
    raw = balance * fraction * leverage / price
    return (int(raw * 10**qty_precision) / (10**qty_precision))
