"""utils.py - 라쉬케5 전략 보조 함수 (최종 안정 + 슬리피지 포함)
 - 수량/가격 정밀도 처리
 - 실시간 잔고 기준 수량 계산
 - 슬리피지 반영 가격 계산 추가
"""

from decimal import Decimal, ROUND_DOWN
from binance_client import get_symbol_precision, client
from risk_config import CAPITAL_USAGE, LEVERAGE, TP_SL_SLIPPAGE_RATE as SLIPPAGE

MIN_NOTIONAL = 5.0  # 최소 주문 금액 (USDT 기준)

def get_futures_balance() -> float:
    balances = client.futures_account_balance()
    for asset in balances:
        if asset["asset"] == "USDT":
            return float(asset["balance"])
    return 0.0

def round_quantity(symbol: str, qty: float) -> float:
    step_size = get_symbol_precision(symbol)["step_size"]
    rounded_qty = float(Decimal(str(qty)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN))
    return max(rounded_qty, float(step_size))

def round_price(symbol: str, price: float) -> float:
    tick_size = get_symbol_precision(symbol)["tick_size"]
    rounded_price = float(Decimal(str(price)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN))
    return max(rounded_price, float(tick_size))

def calculate_order_quantity(symbol: str, price: float, balance: float = None) -> float:
    if balance is None:
        balance = get_futures_balance()
    raw_qty = balance * CAPITAL_USAGE * LEVERAGE / price
    qty = round_quantity(symbol, raw_qty)
    notional = qty * price
    if notional < MIN_NOTIONAL:
        return 0.0
    return qty

def apply_slippage(price: float, side: str) -> float:
    """진입/청산 가격에 슬리피지를 적용한 가격 반환"""
    if side == "LONG":
        return round(price * (1 + SLIPPAGE), 4)
    elif side == "SHORT":
        return round(price * (1 - SLIPPAGE), 4)
    return round(price, 4)

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
