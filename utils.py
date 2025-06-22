"""전략 공통 유틸 함수 모듈"""

import math
from datetime import datetime
from typing import Iterable

from zoneinfo import ZoneInfo

from risk_config import CAPITAL_USAGE, LEVERAGE


def calculate_order_quantity(symbol: str, price: float, balance: float = 1000) -> float:
    """자산, 비율, 레버리지를 기준으로 주문 수량 계산"""
    raw_qty = balance * CAPITAL_USAGE * LEVERAGE / price
    return round_quantity(symbol, raw_qty)


def calculate_rsi(prices: Iterable[float], period: int = 14) -> float:
    """RSI 계산"""
    prices = list(prices)
    if len(prices) < period + 1:
        raise ValueError("RSI 계산을 위한 가격 데이터가 부족합니다")

    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = prices[-i] - prices[-i - 1]
        if delta >= 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period if losses else 0.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def to_kst(dt: datetime) -> datetime:
    """UTC 기준 datetime을 KST로 변환"""
    return dt.astimezone(ZoneInfo("Asia/Seoul"))


def apply_slippage(price: float, side: str, rate: float) -> float:
    """슬리피지를 적용한 TP/SL 가격 계산"""
    if side.upper() == "LONG":
        return price * (1 + rate)
    return price * (1 - rate)


def round_price(symbol: str, price: float, tick_size: float = 0.01) -> float:
    """tick size 기준 가격 반올림 (내림 처리)"""
    return math.floor(price / tick_size) * tick_size


def round_quantity(symbol: str, qty: float, step_size: float = 0.001) -> float:
    """step size 기준 수량 반올림 (내림 처리)"""
    return math.floor(qty / step_size) * step_size
