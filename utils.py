# 파일명: utils.py
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
from binance_client import client
from risk_config import POSITION_RATIO, LEVERAGE, MIN_NOTIONAL


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_trade(data: dict) -> None:
    """trade_log.json에 거래 기록 저장"""
    path = "trade_log.json"
    logs = []
    if os.path.exists(path):
        with open(path, "r") as f:
            logs = json.load(f)
    logs.append(data)
    with open(path, "w") as f:
        json.dump(logs, f, indent=4)


def get_futures_balance() -> float:
    """USDT 선물 계정 잔고 조회"""
    try:
        balances = client.futures_account_balance()
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["balance"])
    except Exception as e:
        logging.error(f"[잔고 조회 오류] {e}")
    return 0.0


def get_lot_size(symbol: str) -> float:
    """심볼별 최소 주문 수량 (LOT_SIZE > stepSize)"""
    try:
        info = client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                for f in s["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        return float(f["stepSize"])
    except Exception as e:
        logging.error(f"[LOT_SIZE 조회 오류] {symbol}: {e}")
    return 0.0


def calculate_order_quantity(symbol: str) -> float:
    """레버리지·포지션 비율·소수점 제한 기반 수량 계산"""
    try:
        balance = Decimal(str(get_futures_balance()))
        position_ratio = Decimal(str(POSITION_RATIO))
        leverage = Decimal(str(LEVERAGE))
        min_notional = Decimal(str(MIN_NOTIONAL))
        amount = balance * position_ratio * leverage

        price = Decimal(str(client.futures_symbol_ticker(symbol=symbol)["price"]))
        raw_qty = amount / price

        step = Decimal(str(get_lot_size(symbol)))
        if step <= 0:
            return 0.0

        precision = -step.as_tuple().exponent
        quant = Decimal(f"1e-{precision}")
        qty = raw_qty.quantize(quant, rounding=ROUND_DOWN)

        # 최소 거래 금액 미달 또는 0이면 무시
        notional = qty * price
        if qty <= Decimal("0") or notional < min_notional:
            return 0.0

        return float(qty)

    except Exception as e:
        logging.error(f"[수량 계산 오류] {symbol}: {e}")
        return 0.0



def extract_entry_price(resp: dict) -> float:
    try:
        return float(resp["avgFillPrice"])
    except:
        try:
            return float(resp["fills"][0]["price"])
        except:
            return 0.0


def summarize_trades() -> str:
    return "📊 누적 손익 요약 준비 중입니다."


def get_filtered_top_symbols(n: int = 100) -> list:
    from utils import get_lot_size
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
            logging.warning(f"[심볼 필터링] {sym} 제거 (minQty 없음)")
    return result


def to_kst(timestamp=None) -> datetime:
    kst = timezone(timedelta(hours=9))
    if timestamp is None:
        return datetime.now(tz=kst)
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=kst)
    if isinstance(timestamp, datetime):
        return timestamp.astimezone(kst)
    raise ValueError("지원되지 않는 timestamp 형식입니다.")
