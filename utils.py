"""utils.py - 라쉬케5 전략 보조 함수 모음
 - 정확한 수량/가격 반올림
 - 심볼별 precision 정보 처리
 - 실시간 수량 계산 (잔고 기준)
"""

from decimal import Decimal, ROUND_DOWN
from binance_client import get_symbol_precision, get_futures_balance
from risk_config import CAPITAL_USAGE, LEVERAGE

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
    """잔고, 비율, 레버리지 기준으로 수량 계산 후 정확히 반올림"""
    if balance is None:
        balance = get_futures_balance()
    raw_qty = balance * CAPITAL_USAGE * LEVERAGE / price
    return round_quantity(symbol, raw_qty)

def to_kst(dt):
    """UTC 시간을 한국 시간으로 변환"""
    from datetime import timedelta
    return dt + timedelta(hours=9)

def calculate_rsi(prices: list, period: int = 14) -> float:
    """RSI 계산 보조 함수 (테스트용)"""
    import numpy as np
    if len(prices) < period:
        return 50
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    return 100 - 100 / (1 + rs)
