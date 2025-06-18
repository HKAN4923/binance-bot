import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()

client = Client(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_API_SECRET")
)

def get_symbol_min_qty(symbol):
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                for f in s["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        return f["minQty"]
        return None
    except Exception as e:
        print(f"[Binance API 오류] 최소 수량 조회 실패: {e}")
        return None

def get_price(symbol):
    try:
        return float(client.get_symbol_ticker(symbol=symbol)["price"])
    except Exception as e:
        print(f"[ERROR] get_price({symbol}): {e}")
        return None

def get_klines(symbol, interval="1h", limit=100):
    try:
        return client.get_klines(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        print(f"[ERROR] get_klines({symbol}, {interval}): {e}")
        return []

def place_market_order(symbol, side, quantity):
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )
        return order
    except Exception as e:
        print(f"[ERROR] place_market_order({symbol}, {side}, {quantity}): {e}")
        return None

def place_market_exit(symbol, side, quantity):
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=True
        )
        return order
    except Exception as e:
        print(f"[ERROR] place_market_exit({symbol}, {side}, {quantity}): {e}")
        return None
