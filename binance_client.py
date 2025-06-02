import os
import math
import time
import logging
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

# 주문 재시도 로직 추가 (핵심 개선)
def create_order_with_retry(order_func, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return order_func(**kwargs)
        except BinanceAPIException as e:
            if e.code in [-1021, -2010, -4046]:  # 타임아웃, 주문량 부족 등
                wait = 1 + attempt * 0.5
                logging.warning(f"주문 재시도 ({attempt+1}/{max_retries}): {e}, {wait}초 대기")
                time.sleep(wait)
            else:
                raise
    return None

def get_open_position_amt(symbol: str) -> float:
    try:
        positions = client.futures_position_information(symbol=symbol)
        for p in positions:
            amt = float(p['positionAmt'])
            if amt != 0:
                return abs(amt)
        return 0.0
    except BinanceAPIException:
        return 0.0

def get_ohlcv(symbol, interval="5m", limit=100):
    try:
        time.sleep(0.05)  # API 호출 제한 방지
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'
        ])
        # 필요한 컬럼만 수치형으로 변환
        for c in ['open','high','low','close','volume']:
            df[c] = pd.to_numeric(df[c])
        return df
    except Exception:
        return None

def change_leverage(symbol, lev):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=lev)
    except Exception:
        pass

def get_balance():
    try:
        bal = client.futures_account_balance()
        return float(next(x for x in bal if x["asset"]=="USDT")["balance"])
    except Exception:
        return 0.0

def get_mark_price(symbol):
    try:
        return float(client.futures_mark_price(symbol=symbol)["markPrice"])
    except Exception:
        return 0.0

def get_precision(symbol):
    info = client.futures_exchange_info()["symbols"]
    f = next((x for x in info if x["symbol"]==symbol), None)
    if not f:
        return 8, 8, 0.0
    p_price = int(-math.log10(float(next(filt for filt in f["filters"] if filt["filterType"]=="PRICE_FILTER")["tickSize"])))
    p_qty = int(-math.log10(float(next(filt for filt in f["filters"] if filt["filterType"]=="LOT_SIZE")["stepSize"])))
    min_qty = float(next(filt for filt in f["filters"] if filt["filterType"]=="LOT_SIZE")["stepSize"])
    return p_price, p_qty, min_qty

def create_market_order(symbol, side, qty, reduceOnly=False):
    return create_order_with_retry(
        client.futures_create_order,
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty,
        reduceOnly=reduceOnly
    )

def create_stop_order(symbol, side, sl_price, qty):
    return create_order_with_retry(
        client.futures_create_order,
        symbol=symbol,
        side=side,
        type="STOP_MARKET",
        stopPrice=sl_price,
        closePosition=True
    )

def create_take_profit(symbol, side, tp_price, qty):
    return create_order_with_retry(
        client.futures_create_order,
        symbol=symbol,
        side=side,
        type="TAKE_PROFIT_MARKET",
        stopPrice=tp_price,
        closePosition=True
    )

def cancel_all_orders_for_symbol(symbol):
    try:
        orders = client.futures_get_open_orders(symbol=symbol)
        for order in orders:
            client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
        logging.info(f"[{symbol}] 기존 주문 전부 취소 완료")
    except BinanceAPIException:
        pass

def create_limit_order(symbol: str, side: str, quantity: float, price: float):
    return create_order_with_retry(
        client.futures_create_order,
        symbol=symbol,
        side=side,
        type="LIMIT",
        timeInForce="GTC",
        quantity=quantity,
        price=price
    )
