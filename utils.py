from decimal import Decimal, ROUND_DOWN, getcontext
import datetime
import pytz

def to_kst(ts: float):
    """
    UTC 타임스탬프를 KST (Asia/Seoul) datetime 객체로 변환
    """
    utc_dt = datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC)
    kst = utc_dt.astimezone(pytz.timezone("Asia/Seoul"))
    return kst

def calculate_qty(balance: float, price: float, leverage: int, fraction: float, qty_precision: int, min_qty: float):
    """
    잔고 balance, 현재가 price, 레버리지 leverage를 활용해
    balance * leverage * fraction 만큼의 자금을 투입한 뒤 price로 나누어 수량을 구합니다.
    Decimal을 사용해 정확도를 높이고, qty_precision 자릿수만큼 소수점 내림(ROUND_DOWN) 처리합니다.
    또한, 최소 주문 수량(min_qty)을 충족하지 못하면 0.0을 반환합니다.
    """
    getcontext().prec = qty_precision + 10
    raw = Decimal(balance) * Decimal(leverage) * Decimal(fraction) / Decimal(price)
    quant = Decimal('1e-{}'.format(qty_precision))
    qty = raw.quantize(quant, rounding=ROUND_DOWN)

    if qty < Decimal(str(min_qty)):
        return 0.0
    return float(qty)
# utils.py

def get_top_100_volume_symbols():
    """
    24시간 거래량 기준 상위 100개 USDT 페어 반환
    """
    from binance_client import client
    import logging

    try:
        stats_24h = client.futures_ticker()
        usdt_pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats_24h
            if s["symbol"].endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [s["symbol"] for s in usdt_pairs[:100]]
    except Exception as e:
        logging.error(f"get_top_100_volume_symbols 오류: {e}")
        return []
