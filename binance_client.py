# 파일명: binance_client.py
# Binance API 호출 래퍼 모듈

import os
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

def get_price(symbol: str) -> float:
    """실시간 가격 조회."""
    try:
        return float(client.futures_symbol_ticker(symbol=symbol)["price"])
    except Exception as e:
        print(f"[가격 조회 오류] {symbol}: {e}")
        return 0.0

def get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> list:
    """캔들 데이터 조회."""
    try:
        return client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        print(f"[캔들 조회 오류] {symbol}: {e}")
        return []

def futures_account_balance() -> float:
    """USDT 선물 계정 잔고 조회 (utils.get_futures_balance()와 연계)."""
    try:
        bal = client.futures_account_balance()
        return float(next(x for x in bal if x["asset"] == "USDT")["balance"])
    except BinanceAPIException as e:
        print(f"[잔고 조회 오류] {e}")
        return 0.0

def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """시장가 진입 주문."""
    try:
        return client.futures_create_order(
            symbol=symbol, side=side, type="MARKET", quantity=quantity
        )
    except BinanceAPIException as e:
        print(f"[시장가 주문 오류] {symbol}: {e}")
        return {}

def place_market_exit(symbol: str, side: str, quantity: float) -> dict:
    """시장가 청산 주문 (reduceOnly=True)."""
    try:
        return client.futures_create_order(
            symbol=symbol, side=side, type="MARKET", quantity=quantity, reduceOnly=True
        )
    except BinanceAPIException as e:
        print(f"[시장가 청산 오류] {symbol}: {e}")
        return {}

def create_limit_order(symbol: str, side: str, quantity: float, price: float) -> dict:
    """지정가 주문 (진입 안정성용)."""
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="LIMIT",
            timeInForce="GTC",
            quantity=quantity,
            price=price
        )
    except BinanceAPIException as e:
        print(f"[지정가 주문 오류] {symbol}: {e}")
        return {}

def create_take_profit(symbol: str, side: str, stop_price: float) -> dict:
    """조건부 익절 주문 (closePosition=True)."""
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=stop_price,
            closePosition=True
        )
    except BinanceAPIException as e:
        print(f"[TP 주문 오류] {symbol}: {e}")
        return {}

def create_stop_order(symbol: str, side: str, stop_price: float) -> dict:
    """조건부 손절 주문 (closePosition=True)."""
    try:
        return client.futures_create_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=stop_price,
            closePosition=True
        )
    except BinanceAPIException as e:
        print(f"[SL 주문 오류] {symbol}: {e}")
        return {}

def cancel_all_orders_for_symbol(symbol: str):
    """
    해당 심볼의 모든 미체결 주문 취소
    """
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
    except Exception as e:
        print(f"[주문 취소 오류] {symbol}: {e}")
