# ✅ WebSocket 가격 fallback 적용된 utils.py 전체 통합본

import math
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from binance_client import client
from price_ws import get_price as ws_price  # ✅ 실시간 가격 fallback
from risk_config import CAPITAL_USAGE

def get_candles(symbol: str, interval: str = "5m", limit: int = 100):
    try:
        return client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        logging.error(f"[utils] 칸들 조회 오류: {symbol} - {e}")
        return []

def get_price(symbol: str):
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = ticker.get("price")
        if price is None:
            fallback = ws_price(symbol)
            logging.warning(f"[REST 실패] {symbol} → WebSocket 가격 대체: {fallback}")
            return fallback
        return float(price)
    except Exception as e:
        logging.error(f"[utils] 가격 조회 오류: {symbol} - {e}")
        return ws_price(symbol)

def calculate_ema(values, period):
    if len(values) < period:
        return None
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    a = np.convolve(values, weights, mode='full')[:len(values)]
    a[:period] = a[period]
    return list(a)

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = [100 - 100 / (1 + rs)]
    for delta in deltas[period:]:
        upval = max(delta, 0)
        downval = -min(delta, 0)
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi.append(100 - 100 / (1 + rs))
    return rsi

def round_quantity(symbol: str, qty: float):
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                step_size = float([f for f in s["filters"] if f["filterType"] == "LOT_SIZE"][0]["stepSize"])
                precision = int(round(-math.log(step_size, 10), 0))
                return round(qty, precision)
    except Exception as e:
        logging.error(f"[utils] 수량 반올림 오류: {symbol} - {e}")
    return qty

def round_price(symbol: str, price: float):
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                tick_size = float([f for f in s["filters"] if f["filterType"] == "PRICE_FILTER"][0]["tickSize"])
                precision = int(round(-math.log(tick_size, 10), 0))
                return round(price, precision)
    except Exception as e:
        logging.error(f"[utils] 가격 반올림 오류: {symbol} - {e}")
    return price

def get_futures_balance():
    try:
        balances = client.futures_account_balance()
        usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
        return float(usdt['balance']) if usdt else 0.0
    except Exception as e:
        logging.error(f"[utils] 장복 조회 오류: {e}")
        return 0.0

def calculate_order_quantity(symbol: str, price: float, balance: float):
    try:
        usdt_amount = balance * CAPITAL_USAGE
        quantity = usdt_amount / price
        return quantity
    except Exception as e:
        logging.error(f"[utils] 수량 계산 오류: {e}")
        return 0.0

def cancel_all_orders(symbol: str):
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
    except Exception as e:
        logging.error(f"[utils] 주문 취소 오류: {symbol} - {e}")

def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=9)))
