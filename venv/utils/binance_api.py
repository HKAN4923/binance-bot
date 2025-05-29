# utils/binance_api.py

import ccxt
from config import API_KEY, API_SECRET

exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {"defaultType": "future"}
})

def fetch_ohlcv(symbol, interval, limit):
    return exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)

def fetch_ticker(symbol):
    return exchange.fetch_ticker(symbol)["last"]

def create_market_order(symbol, side, amount):
    if side == "long":
        return exchange.create_market_buy_order(symbol, amount)
    else:
        return exchange.create_market_sell_order(symbol, amount)

def create_tp_sl_orders(symbol, side, amount, tp, sl):
    # Take profit
    exchange.create_order(
        symbol, "TAKE_PROFIT_MARKET",
        "sell" if side=="long" else "buy",
        amount, None, {"stopPrice":tp,"closePosition":True}
    )
    # Stop loss
    exchange.create_order(
        symbol, "STOP_MARKET",
        "sell" if side=="long" else "buy",
        amount, None, {"stopPrice":sl,"closePosition":True}
    )
