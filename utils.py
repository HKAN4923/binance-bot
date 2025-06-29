"""utils.py - 라쉬케5 전략 보조 함수 (최종 안정 + 슬리피지 포함)
 - 수량/가격 정밀도 처리
 - 실시간 잔고 기준 수량 계산
 - 슬리피지 반영 가격 계산 추가
"""
import logging
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

def calculate_order_quantity(symbol: str, entry_price: float, balance: float) -> float:
    """
    잔고, 진입 가격, 설정값 기준으로 수량 계산
    - 최소 수량 제한
    - 최소 주문 금액 제한 (레버리지 포함)
    - step_size 절삭
    """
    try:
        precision = get_symbol_precision(symbol)
        step_size = precision["step_size"]

        capital = balance * CAPITAL_USAGE
        raw_qty = (capital * LEVERAGE) / entry_price
        quantity = round_quantity(symbol, raw_qty)
        notional = quantity * entry_price * LEVERAGE  # ✅ 레버리지 포함 기준

        if quantity <= 0:
            logging.warning(f"[경고] 수량이 0입니다: {symbol} → 계산된 수량이 step_size보다 작음")
            return 0.0
        if notional < MIN_NOTIONAL:
            logging.warning(f"[경고] {symbol} 주문 금액 {notional:.4f} USDT < 최소 {MIN_NOTIONAL} USDT")
            return 0.0

        return quantity

    except Exception as e:
        logging.error(f"[오류] 수량 계산 실패: {e}")
        return 0.0

def apply_slippage(price: float, side: str, rate: float) -> float:
    if side.upper() == "LONG":
        return round(price * (1 + rate), 4)
    elif side.upper() == "SHORT":
        return round(price * (1 - rate), 4)
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

def cancel_all_orders(symbol: str) -> None:
    """지정된 심볼의 모든 미체결 주문 취소"""
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
       
    except Exception as e:
        logging.error(f"[오류] {symbol} 주문 정리 실패: {e}")
