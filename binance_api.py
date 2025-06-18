# binance_api.py
import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

def get_price(symbol):
    try:
        res = client.futures_symbol_ticker(symbol=symbol)
        return float(res["price"])
    except Exception as e:
        print(f"[가격 조회 오류] {symbol}: {e}")
        return None

def get_klines(symbol, interval="1h", limit=100):
    try:
        return client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        print(f"[캔들 조회 오류] {symbol}: {e}")
        return []

def get_futures_balance():
    try:
        balances = client.futures_account_balance()
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["balance"])
        return None
    except Exception as e:
        print(f"[잔고 조회 오류] {e}")
        return None

def get_lot_size(symbol):
    try:
        info = client.futures_exchange_info()
        for item in info["symbols"]:
            if item["symbol"] == symbol:
                for f in item["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        return float(f["minQty"])
        return None
    except Exception as e:
        print(f"[수량 단위 조회 오류] {symbol}: {e}")
        return None

def get_lot_precision(symbol):
    try:
        info = client.futures_exchange_info()
        for item in info["symbols"]:
            if item["symbol"] == symbol:
                for f in item["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        min_qty = float(f["minQty"])
                        precision = abs(int(round(-1 * (min_qty).as_integer_ratio()[1] ** -1).bit_length()))
                        return precision
        return 3  # 기본값
    except Exception as e:
        print(f"[수량 정밀도 조회 오류] {symbol}: {e}")
        return 3

def place_market_order(symbol, side, quantity):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )
    except Exception as e:
        print(f"[시장가 주문 오류] {symbol}: {e}")
        return {}

def place_market_exit(symbol, side, quantity):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=True
        )
    except Exception as e:
        print(f"[시장가 청산 오류] {symbol}: {e}")
        return {}

def create_take_profit(symbol, side, quantity, target_price):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=target_price,
            closePosition=False,
            quantity=quantity,
            timeInForce="GTC",
            reduceOnly=True
        )
    except Exception as e:
        print(f"[TP 주문 오류] {symbol}: {e}")
        return {}

def create_stop_order(symbol, side, quantity, stop_price):
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=stop_price,
            closePosition=False,
            quantity=quantity,
            timeInForce="GTC",
            reduceOnly=True
        )
    except Exception as e:
        print(f"[SL 주문 오류] {symbol}: {e}")
        return {}
