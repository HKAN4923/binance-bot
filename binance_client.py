# ✅ binance_client.py (추가된 함수 포함)

import os
import logging
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

def get_price(symbol: str) -> float:
    try:
        return float(client.futures_symbol_ticker(symbol=symbol)["price"])
    except Exception as e:
        logging.error(f"[가격 조회 오류] {symbol}: {e}")
        return 0.0

# ✅ 포지션 종료 후 남아있는 청산용 주문 삭제용

def cancel_exit_orders_for_symbol(symbol: str):
    """
    포지션 종료 후 남아있을 수 있는 TP/SL (reduceOnly) 주문을 모두 삭제합니다.
    """
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            if order.get("reduceOnly"):
                client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                logging.info(f"[청산 주문 삭제] {symbol} 주문 ID: {order['orderId']}")
    except Exception as e:
        logging.error(f"[청산 주문 삭제 오류] {symbol}: {e}")
