# utils.py (수정본)
from decimal import Decimal, ROUND_DOWN, getcontext
import datetime
import pytz
import logging

# 계산: 익절가, 손절가

def calculate_tp_sl(entry_price, tp_percent, sl_percent, side):
    tp = entry_price * (1 + tp_percent / 100) if side == "long" else entry_price * (1 - tp_percent / 100)
    sl = entry_price * (1 - sl_percent / 100) if side == "long" else entry_price * (1 + sl_percent / 100)
    return round(tp, 2), round(sl, 2)

# 현재시간을 KST로 변환

def to_kst(ts: float):
    utc_dt = datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC)
    return utc_dt.astimezone(pytz.timezone("Asia/Seoul"))

# 수량 계산 (소수점 반영, 최소 수량 필터)

def calculate_qty(balance: float, price: float, leverage: int, fraction: float, qty_precision: int, min_qty: float):
    getcontext().prec = qty_precision + 10
    raw = Decimal(balance) * Decimal(leverage) * Decimal(fraction) / Decimal(price)
    quant = Decimal('1e-{}'.format(qty_precision))
    qty = raw.quantize(quant, rounding=ROUND_DOWN)
    if qty < Decimal(str(min_qty)):
        return 0.0
    return float(qty)

# 거래량 상위 100개 심볼

def get_top_100_volume_symbols():
    from binance_api import client
    try:
        stats_24h = client.futures_ticker()
        usdt_pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats_24h if s["symbol"].endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [s["symbol"] for s in usdt_pairs[:100]]
    except Exception as e:
        logging.error(f"get_top_100_volume_symbols 오류: {e}")
        return []

# 거래 가능한 심볼 필터

def get_tradable_futures_symbols():
    from binance_api import client
    try:
        exchange_info = client.futures_exchange_info()
        symbols = [
            s["symbol"] for s in exchange_info["symbols"]
            if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
        ]
        return symbols
    except Exception as e:
        logging.error(f"get_tradable_futures_symbols 오류: {e}")
        return []

# 가격 소수점 단위

def get_tick_size(symbol: str):
    from binance_api import client
    from decimal import Decimal
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    return Decimal(str(f['tickSize']))
    return Decimal("0.01")
