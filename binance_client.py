# binance_client.py
from binance.client import Client
import os
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize Binance client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
client.FUTURES_URL = 'https://fapi.binance.com'

# Set leverage
def set_leverage(symbols, leverage=5):
    """
    Set leverage for all symbols
    """
    for sym in symbols:
        try:
            client.futures_change_leverage(symbol=sym, leverage=leverage)
        except Exception as e:
            print(f"[Leverage Error] {sym}: {e}")

# Get candlestick data
def get_klines(symbol, interval, limit=100):
    """
    Get candlestick data from Binance Futures
    """
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_asset_vol','num_trades','taker_base_vol','taker_quote_vol','ignore'
    ])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df[['open_time','open','high','low','close','volume']]

# Place market order
def place_order(symbol, side, quantity):
    """
    Place a market order
    """
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=quantity
    )

# Get current position
def get_open_position(symbol):
    """
    Get current open position
    """
    pos = client.futures_position_information(symbol=symbol)
    for p in pos:
        amt = float(p['positionAmt'])
        if amt != 0:
            return p
    return None

# Get mark price
def get_mark_price(symbol):
    """
    Get current mark price
    """
    res = client.futures_mark_price(symbol=symbol)
    return float(res['markPrice'])

# Set stop loss and take profit
def set_sl_tp(symbol, side, sl_price, tp_price, quantity):
    """
    Set stop loss and take profit orders
    """
    try:
        # OCO: STOP_MARKET + TAKE_PROFIT_MARKET
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='STOP_MARKET',
            stopPrice=sl_price,
            closePosition=True
        )
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price,
            closePosition=True
        )
    except Exception as e:
        print(f"[SL/TP Error] {symbol}: {e}")

# 잔고 조회 함수 (USDT 잔고 확인용)
def get_balance():
    balances = client.futures_account_balance()
    for b in balances:
        if b['asset'] == 'USDT':
            return float(b['balance'])
    return 0.0
