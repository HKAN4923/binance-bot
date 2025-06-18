# binance_api.py
import os
import time
import requests
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

def get_price(symbol):
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except Exception as e:
        print(f"[가격 조회 실패] {symbol}: {e}")
        return None

def get_futures_balance():
    try:
        balances = client.futures_account_balance()
        for b in balances:
            if b["asset"] == "USDT":
                return float(b["balance"])
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
                        return {
                            "minQty": float(f["minQty"]),
                            "stepSize": float(f["stepSize"])
                        }
    except Exception as e:
        print(f"[로트 크기 조회 실패] {symbol}: {e}")
        return None

def place_market_order(symbol, side, quantity):
    try:
        response = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=FUTURE_ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print(f"[시장가 주문 체결] {symbol} {side} {quantity}")
        return response
    except Exception as e:
        print(f"[시장가 주문 실패] {symbol}: {e}")
        return None

def place_market_exit(symbol, side, quantity):
    return place_market_order(symbol, side, quantity)

def create_take_profit(symbol, side, quantity, tp_price):
    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=tp_price,
            closePosition=True,
            timeInForce="GTC"
        )
        print(f"[TP 설정 완료] {symbol} @ {tp_price}")
    except Exception as e:
        print(f"[TP 설정 실패] {symbol}: {e}")

def create_stop_order(symbol, side, quantity, sl_price):
    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=sl_price,
            closePosition=True,
            timeInForce="GTC"
        )
        print(f"[SL 설정 완료] {symbol} @ {sl_price}")
    except Exception as e:
        print(f"[SL 설정 실패] {symbol}: {e}")
