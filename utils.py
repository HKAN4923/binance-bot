# utils.py

import os
import logging
from decimal import Decimal, getcontext, ROUND_DOWN
import pandas as pd
from binance_client import client, get_price

# 소수점 정밀도
getcontext().prec = 18

# 포지션당 진입 비율 (기본 자산의 20%)
ALLOC_RATIO = Decimal(os.getenv("ALLOC_RATIO", "0.2"))


def calculate_order_quantity(symbol: str) -> float:
    """
    현재 USDT 잔고의 ALLOC_RATIO 비율만큼
    해당 심볼 포지션 수량을 계산하여 반환합니다.
    """
    try:
        balances = client.futures_account_balance()
        balance_usdt = Decimal(
            next(b["balance"] for b in balances if b["asset"] == "USDT")
        )
    except Exception as e:
        logging.error(f"[잔고 조회 오류] {e}")
        return 0.0

    price = Decimal(str(get_price(symbol)))
    if price <= 0:
        return 0.0

    qty = (balance_usdt * ALLOC_RATIO) / price
    return float(qty.quantize(Decimal("1e-8"), rounding=ROUND_DOWN))


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI 지표를 계산하여 반환합니다.
    """
    delta = prices.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1 / period, adjust=False).mean()
    ma_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

from datetime import datetime, timedelta

def to_kst(dt: datetime) -> datetime:
    """
    UTC → KST (UTC+9) 변환
    """
    return dt + timedelta(hours=9)
