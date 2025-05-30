import os
import math
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

def get_all_symbols():
    info = client.futures_exchange_info()
    return [s["symbol"] for s in info["symbols"] if s["symbol"].endswith("USDT")]

def get_ohlcv(symbol, interval="5m", limit=100):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'
        ])
        for c in ['open','high','low','close']:
            df[c] = pd.to_numeric(df[c])
        return df
    except Exception:
        return None

def change_leverage(symbol, lev):
    client.futures_change_leverage(symbol=symbol, leverage=lev)

def get_balance():
    bal = client.futures_account_balance()
    return float(next(x for x in bal if x["asset"]=="USDT")["balance"])

def get_mark_price(symbol):
    return float(client.futures_mark_price(symbol=symbol)["markPrice"])

def get_precision(symbol):
    info = client.futures_exchange_info()["symbols"]
    f = next(x for x in info if x["symbol"]==symbol)
    p_price = int(-math.log10(float(next(filt for filt in f["filters"] if filt["filterType"]=="PRICE_FILTER")["tickSize"])))
    p_qty   = int(-math.log10(float(next(filt for filt in f["filters"] if filt["filterType"]=="LOT_SIZE")["stepSize"])))
    return p_price, p_qty

def create_market_order(symbol, side, qty, reduceOnly=False):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty,
        reduceOnly=reduceOnly
    )

def create_stop_order(symbol, side, stop_price, qty):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type="STOP_MARKET",
        stopPrice=stop_price,
        closePosition=True
    )

def create_take_profit(symbol, side, tp_price, qty):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type="TAKE_PROFIT_MARKET",
        stopPrice=tp_price,
        closePosition=True
    )
