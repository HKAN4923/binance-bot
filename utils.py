import time
import datetime
import pytz
import logging
from decimal import Decimal, ROUND_DOWN
from binance_client import CLIENT

def to_kst(ts: float) -> datetime.datetime:
    utc = datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC)
    return utc.astimezone(pytz.timezone("Asia/Seoul"))

def calculate_qty(balance: float, price: float, leverage: int, fraction: float, precision: int, min_qty: float) -> float:
    raw = Decimal(balance) * Decimal(leverage) * Decimal(fraction) / Decimal(price)
    quant = Decimal(f"1e-{precision}")
    qty = raw.quantize(quant, rounding=ROUND_DOWN)
    return float(qty) if qty >= Decimal(str(min_qty)) else 0.0

def get_top_100_volume_symbols() -> list:
    try:
        stats = CLIENT.futures_ticker()
        pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats if s["symbol"].endswith("USDT")
        ]
        pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [p["symbol"] for p in pairs[:100]]
    except Exception as e:
        logging.error(f"get_top_100_volume_symbols 오류: {e}")
        return []

def get_ohlcv(symbol: str, interval: str="5m", limit: int=100):
    import pandas as pd
    try:
        time.sleep(0.05)
        klines = CLIENT.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","qa","nt","tb","tq","ignore"
        ])
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c])
        return df
    except:
        return None
