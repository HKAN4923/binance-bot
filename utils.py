"""utils.py - 라쉬케5 전략 보조 함수 (최종 안정 버전)
 - 수량/가격 정밀도 반올림
 - 실시간 잔고 기준 수량 계산
 - 최소 주문 금액 필터 포함
"""

from decimal import Decimal, ROUND_DOWN
from binance_client import get_symbol_precision, client
from risk_config import CAPITAL_USAGE, LEVERAGE

MIN_NOTIONAL = 5.0  # 최소 주문 금액 (USDT 기준)

def get_futures_balance() -> float:
    """바이낸스 선물 계정의 USDT 잔고 반환"""
    balances = client.futures_account_balance()
    for asset in balances:
        if asset["asset"] == "USDT":
            return float(asset["balance"])
    return 0.0

def round_quantity(symbol: str, qty: float) -> float:
    """심볼별 수량 반올림 (step_size 기준)"""
    step_size = get_symbol_precision(symbol)["step_size"]
    rounded_qty = float(Decimal(str(qty)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN))
    return max(rounded_qty, float(step_size))

def round_price(symbol: str, price: float) -> float:
    """심볼별 가격 반올림 (tick_size 기준)"""
    tick_size = get_symbol_precision(symbol)["tick_size"]
    rounded_price = float(Decimal(str(price)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN))
    return max(rounded_price, float(tick_size))

def calculate_order_quantity(symbol: str, price: float, balance: float = None) -> float:
    """잔고, 비율, 레버리지 기준으로 수량 계산 후 정밀도 처리 및 최소 notional 체크"""
    if balance is None:
        balance = get_futures_balance()
    raw_qty = balance * CAPITAL_USAGE * LEVERAGE / price
    qty = round_quantity(symbol, raw_qty)
    notional = qty * price
    if notional < MIN_NOTIONAL:
        return 0.0  # 최소 주문 금액 미만이면 진입하지 않음
    return qty

def to_kst(dt):
    from datetime import timedelta
    return dt + timedelta(hours=9)

def calculate_rsi(prices: list, period: int = 14) -> float:
    import numpy as np
    if len(prices) < period:
        return 50
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    return 100 - 100 / (1 + rs)
