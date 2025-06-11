# utils.py
import os
import csv
import math
from datetime import datetime, timedelta
import requests
from binance_api import get_balance, get_price
from risk_config import POSITION_RATIO, LEVERAGE

# --- Exchange info caching for symbol filters ---
_EXCHANGE_INFO = None

def _load_exchange_info():
    global _EXCHANGE_INFO
    if _EXCHANGE_INFO is None:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        _EXCHANGE_INFO = requests.get(url).json()
    return _EXCHANGE_INFO

def _get_symbol_filters(symbol: str) -> list:
    info = _load_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            return s.get("filters", [])
    return []

# --- Step size, min qty, min notional ---
def get_step_size(symbol: str) -> float:
    for f in _get_symbol_filters(symbol):
        if f.get("filterType") in ("LOT_SIZE", "MARKET_LOT_SIZE"):
            return float(f.get("stepSize", 0))
    return 0.0

def get_min_qty(symbol: str) -> float:
    for f in _get_symbol_filters(symbol):
        if f.get("filterType") in ("LOT_SIZE", "MARKET_LOT_SIZE"):
            return float(f.get("minQty", 0))
    return 0.0

def get_min_notional(symbol: str) -> float:
    for f in _get_symbol_filters(symbol):
        if f.get("filterType") == "MIN_NOTIONAL":
            return float(f.get("minNotional", 0))
    return 0.0

# --- Quantity rounding ---
def round_quantity(qty: float, step_size: float) -> float:
    """
    Round down to nearest step_size.
    """
    if step_size <= 0:
        return 0.0
    precision = int(round(-math.log10(step_size)))
    floored = math.floor(qty / step_size) * step_size
    return round(floored, precision)

# --- Order quantity calculation ---
def calculate_order_quantity(symbol: str) -> float:
    """
    Calculate order quantity based on balance, leverage, position ratio.
    Ensures step size, min quantity, and min notional requirements.
    Returns 0.0 if requirements not met.
    """
    balance = get_balance()
    usdt_to_use = balance * POSITION_RATIO * LEVERAGE
    price = get_price(symbol)

    # raw quantity in units
    raw_qty = usdt_to_use / price if price > 0 else 0.0
    step = get_step_size(symbol)
    min_qty = get_min_qty(symbol)
    min_notional = get_min_notional(symbol)

    qty = round_quantity(raw_qty, step)

    # Requirements
    if qty < min_qty:
        return 0.0
    if min_notional and qty * price < min_notional:
        return 0.0
    return qty

# --- Time utilities ---
def utc_to_kst(utc_dt: datetime) -> datetime:
    return utc_dt + timedelta(hours=9)

def now_string() -> str:
    return utc_to_kst(datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S')

# --- TP/SL calculation ---
def calculate_tp_sl(entry_price: float, tp_percent: float, sl_percent: float, side: str):
    if side == "long":
        tp = entry_price * (1 + tp_percent / 100)
        sl = entry_price * (1 - sl_percent / 100)
    else:
        tp = entry_price * (1 - tp_percent / 100)
        sl = entry_price * (1 + sl_percent / 100)
    return round(tp, 4), round(sl, 4)

# --- Logging trades ---
def log_trade(data: dict, file_path='trade_log.csv'):
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# --- Slippage calculation ---
def calculate_slippage(expected_price: float, actual_price: float) -> float:
    return round(abs(expected_price - actual_price) / expected_price * 100, 3)

# --- Extract entry price safely ---
def extract_entry_price(resp: dict) -> float | None:
    """
    Return executed price from Binance order response safely.
    Checks 'fills', 'avgPrice', 'price' without raising errors.
    """
    if not isinstance(resp, dict):
        return None
    # fills first
    fills = resp.get('fills')
    if isinstance(fills, list) and fills:
        try:
            return float(fills[0].get('price', 0))
        except (TypeError, ValueError):
            pass
    # avgPrice fallback
    avg = resp.get('avgPrice')
    if avg not in (None, '', '0'):
        try:
            return float(avg)
        except (TypeError, ValueError):
            pass
    # price fallback
    pr = resp.get('price')
    if pr not in (None, '', '0'):
        try:
            return float(pr)
        except (TypeError, ValueError):
            pass
    return None
