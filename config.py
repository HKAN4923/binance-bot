# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Binance API
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# Telegram Bot
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Trading Settings
LEVERAGE = 5
HEARTBEAT_INTERVAL = 3600  # seconds
USDT_RISK_PER_TRADE = 50   # USDT per entry
SYMBOLS = ['BTCUSDT', 'ETHUSDT']  # 거래 대상 심볼 리스트

# ------------------------------------------------------------------------------
# binance_client.py
from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET, LEVERAGE

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
client.FUTURES_URL = 'https://fapi.binance.com'

# 모든 심볼에 레버리지 설정
def set_leverage(symbols):
    for sym in symbols:
        try:
            client.futures_change_leverage(symbol=sym, leverage=LEVERAGE)
        except Exception as e:
            print(f"[Leverage Error] {sym}: {e}")

# 캔들 데이터 가져오기
import pandas as pd

def get_klines(symbol, interval, limit=100):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_asset_vol','num_trades','taker_base_vol','taker_quote_vol','ignore'
    ])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df[['open_time','open','high','low','close','volume']]

# 시장가 주문
def place_order(symbol, side, quantity):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=quantity
    )

# 현재 포지션 조회
def get_open_position(symbol):
    pos = client.futures_position_information(symbol=symbol)
    for p in pos:
        amt = float(p['positionAmt'])
        if amt != 0:
            return p
    return None

# 마크 가격 조회
def get_mark_price(symbol):
    res = client.futures_mark_price(symbol=symbol)
    return float(res['markPrice'])

# 손절/익절 OCO 주문
def set_sl_tp(symbol, side, sl_price, tp_price, quantity):
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