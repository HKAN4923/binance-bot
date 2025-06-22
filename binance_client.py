"""Binance 실전 API 클라이언트"""

import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# 심볼별 정밀도 캐시
_symbol_precision_cache = {}


def get_symbol_precision(symbol: str) -> dict:
    """심볼별 tickSize/stepSize 반환"""
    if symbol in _symbol_precision_cache:
        return _symbol_precision_cache[symbol]

    exchange_info = client.futures_exchange_info()
    for s in exchange_info["symbols"]:
        if s["symbol"] == symbol:
            filters = {f["filterType"]: f for f in s["filters"]}
            step_size = float(filters["LOT_SIZE"]["stepSize"])
            tick_size = float(filters["PRICE_FILTER"]["tickSize"])
            _symbol_precision_cache[symbol] = {
                "step_size": step_size,
                "tick_size": tick_size,
            }
            return _symbol_precision_cache[symbol]

    return {"step_size": 0.001, "tick_size": 0.01}  # 기본값
