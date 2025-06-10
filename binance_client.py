# binance_client.py
import os
import math
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

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
        time.sleep(0.05)
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'
        ])
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
    p_qty   = int(-math.log10(float(next(filt for filt in f["filters"] if filt["filterType"]=="LOT_SIZE")["stepSize"])))
    min_qty = float(next(filt for filt in f["filters"] if filt["filterType"]=="LOT_SIZE")["stepSize"])
    return p_price, p_qty, min_qty

def create_market_order(symbol, side, qty, reduceOnly=False):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=qty,
            reduceOnly=reduceOnly
        )
    except Exception:
        return None

def create_stop_order(symbol, side, sl_price, qty):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=sl_price,
            closePosition=True
        )
    except Exception:
        return None

def create_take_profit(symbol, side, tp_price, qty):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=tp_price,
            closePosition=True
        )
    except Exception:
        return None

def cancel_all_orders_for_symbol(symbol):
    try:
        orders = client.futures_get_open_orders(symbol=symbol)
        for order in orders:
            client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
        print(f"[{symbol}] 기존 주문 전부 취소 완료")
    except BinanceAPIException:
        pass

def create_limit_order(symbol: str, side: str, quantity: float, price: float):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="LIMIT",
            timeInForce="GTC",
            quantity=quantity,
            price=price
        )
    except Exception:
        return None
