# 파일명: utils.py
# 공통 유틸리티 함수 모듈
import os
import json
import logging
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from binance_client import client  # Binance REST 클라이언트
from risk_config import POSITION_RATIO, LEVERAGE, MIN_NOTIONAL  # 자산 비율·레버리지 등 설정 :contentReference[oaicite:0]{index=0}

def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_trade(data: dict) -> None:
    """trade_log.json에 거래 기록을 쌓습니다."""
    path = "trade_log.json"
    logs = []
    if os.path.exists(path):
        with open(path, "r") as f:
            logs = json.load(f)
    logs.append(data)
    with open(path, "w") as f:
        json.dump(logs, f, indent=4)

def get_futures_balance() -> float:
    """USDT 선물 계정 잔고 조회."""
    try:
        balances = client.futures_account_balance()
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["balance"])
    except Exception as e:
        logging.error(f"[잔고 조회 오류] {e}")
    return 0.0

def get_lot_size(symbol: str) -> float:
    """심볼별 최소 주문 수량(minQty) 조회."""
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                for f in s["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        return float(f["minQty"])
    except Exception as e:
        logging.error(f"[수량 단위 조회 오류] {symbol}: {e}")
    return 0.0

def calculate_order_quantity(symbol: str) -> float:
    """
    포지션 비율(POSITION_RATIO)과 레버리지(LEVERAGE)를 적용해
    최적 주문 수량을 계산합니다. 최소 Notional 기준(MIN_NOTIONAL) 미달 시 0 반환.
    """
    balance = get_futures_balance()
    amount = balance * POSITION_RATIO * LEVERAGE
    price = client.futures_symbol_ticker(symbol=symbol)["price"]
    try:
        price = float(price)
    except:
        return 0.0

    raw_qty = Decimal(amount) / Decimal(price)
    # Binance가 허용하는 소수점 자릿수로 반내림
    step = Decimal(str(get_lot_size(symbol)))
    precision = -step.as_tuple().exponent
    quant = Decimal(f"1e-{precision}")
    qty = raw_qty.quantize(quant, rounding=ROUND_DOWN)

    # 최소 Notional 미달 또는 qty 0 이면 진입 불가
    if qty <= 0 or float(qty) * price < MIN_NOTIONAL:
        return 0.0
    return float(qty)

def extract_entry_price(resp: dict) -> float:
    """시장가 체결 응답에서 체결 가격(avgFillPrice) 추출."""
    try:
        return float(resp["avgFillPrice"])
    except:
        try:
            return float(resp["fills"][0]["price"])
        except:
            return 0.0

def summarize_trades() -> str:
    """누적 손익 요약 메시지 생성 (추후 개선 가능)."""
    return "📊 누적 손익 요약 준비 중입니다."

def get_filtered_top_symbols(n: int = 100) -> list:
    """
    1) PERPETUAL·USDT·TRADING 심볼만 추출
    2) 24h 거래량 상위 n개 필터
    3) minQty 정보 있는 심볼만 리턴 (로그에 제거 대상 기록)
    """
    from utils import get_lot_size  # 재귀 import 주의
    tradable = {
        s["symbol"]
        for s in client.futures_exchange_info()["symbols"]
        if s["contractType"] == "PERPETUAL"
        and s["quoteAsset"] == "USDT"
        and s["status"] == "TRADING"
    }
    stats = client.futures_ticker()
    pairs = [
        (s["symbol"], float(s["quoteVolume"]))
        for s in stats
        if s["symbol"].endswith("USDT") and s["symbol"] in tradable
    ]
    pairs.sort(key=lambda x: x[1], reverse=True)
    result = []
    for sym, _ in pairs[:n]:
        step = get_lot_size(sym)
        if step and step > 0:
            result.append(sym)
        else:
            logging.warning(f"[심볼 필터링] {sym} 제거 (minQty 정보 없음)")  
    return result

from datetime import datetime, timezone, timedelta

def to_kst(timestamp=None) -> datetime:
    """
    UTC timestamp 또는 datetime 객체를 KST로 변환
    """
    kst = timezone(timedelta(hours=9))
    if timestamp is None:
        return datetime.now(tz=kst)
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=kst)
    if isinstance(timestamp, datetime):
        return timestamp.astimezone(kst)
    raise ValueError("지원되지 않는 timestamp 형식입니다.")
