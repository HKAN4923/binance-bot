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
