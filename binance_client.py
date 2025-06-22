# binance_client.py (전체 작성)

import os
import logging
import time
from decimal import Decimal
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Load API keys from .env
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

# 가격 조회
def get_price(symbol: str) -> float:
    try:
        return float(client.futures_symbol_ticker(symbol=symbol)["price"])
    except Exception as e:
        logging.error(f"[가격 조회 오류] {symbol}: {e}")
        return 0.0

# 잔고 조회 (USDT 기준)
def get_balance() -> float:
    try:
        balances = client.futures_account_balance()
        usdt_balance = next(b for b in balances if b["asset"] == "USDT")
        return float(usdt_balance["balance"])
    except Exception as e:
        logging.error(f"[잔고 조회 오류] {e}")
        return 0.0

# 캔들 데이터 조회 (OHLCV)
def get_ohlcv(symbol: str, interval: str = "1h", limit: int = 100):
    try:
        time.sleep(0.05)
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        return df
    except Exception as e:
        logging.error(f"[캔들 조회 오류] {symbol}: {e}")
        return None

# 24시간 거래량 상위 심볼 조회
def get_top_volume_symbols(limit: int = 50) -> list:
    try:
        stats = client.futures_ticker()
        usdt_pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats if s["symbol"].endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [p["symbol"] for p in usdt_pairs[:limit]]
    except Exception as e:
        logging.error(f"[심볼 조회 오류] {e}")
        return []

# 레버리지 설정
def change_leverage(symbol: str, leverage: int):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except BinanceAPIException as e:
        logging.error(f"[레버리지 설정 오류] {symbol}: {e}")

# 청산용 주문 삭제 (TP/SL)
def cancel_exit_orders_for_symbol(symbol: str):
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            if order.get("reduceOnly"):
                client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                logging.info(f"[청산 주문 삭제] {symbol} 주문 ID: {order['orderId']}")
    except Exception as e:
        logging.error(f"[청산 주문 삭제 오류] {symbol}: {e}")