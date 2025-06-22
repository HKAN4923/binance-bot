# binance_client.py
import os
import logging
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal, ROUND_DOWN

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)


def get_open_position_amt(symbol: str) -> float:
    positions = client.futures_position_information(symbol=symbol)
    for p in positions:
        amt = float(p['positionAmt'])
        if amt != 0:
            return abs(amt)
    return 0.0


def get_ohlcv(symbol: str, interval: str = "5m", limit: int = 100):
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
    except Exception as e:
        logging.error(f"[캔들 조회 오류] {symbol}: {e}")
        return None


def get_price(symbol: str) -> float:
    try:
        return float(client.futures_symbol_ticker(symbol=symbol)["price"])
    except Exception as e:
        logging.error(f"[가격 조회 오류] {symbol}: {e}")
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 24시간 거래량 상위 심볼 조회  
def get_top_volume_symbols(limit: int = 50) -> list:
    """
    24h 거래량(quoteVolume) 기준으로 USDT 페어를 내림차순 정렬하여
    상위 `limit`개 심볼을 반환합니다.
    """
    try:
        stats = client.futures_ticker()
        usdt_pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats
            if s["symbol"].endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [p["symbol"] for p in usdt_pairs[:limit]]
    except Exception as e:
        logging.error(f"[심볼 조회 오류] {e}")
        return []


def change_leverage(symbol: str, lev: int):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=lev)
    except BinanceAPIException as e:
        logging.error(f"[레버리지 설정 오류] {symbol}: {e}")


# … 이하 기존 주문/체결 함수들 동일 …
