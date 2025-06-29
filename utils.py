"""utils.py - 라쉬케5 전략 보조 유틸리티
 - 수량/가격 정밀도 처리
 - 슬리피지 반영
 - RSI 계산
 - 주문 수량 계산
 - 미체결 주문 정리
"""
import logging
from decimal import Decimal, ROUND_DOWN
from datetime import timedelta

from binance_client import get_symbol_precision, client
from risk_config import CAPITAL_USAGE, LEVERAGE, TP_SL_SLIPPAGE_RATE as SLIPPAGE

MIN_NOTIONAL = 5.0  # 최소 주문 금액 (USDT 기준)


def get_futures_balance() -> float:
    """USDT 기준 실시간 선물 잔고 반환"""
    try:
        balances = client.futures_account_balance()
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["balance"])
    except Exception as e:
        logging.error(f"[오류] 잔고 조회 실패: {e}")
    return 0.0


def round_quantity(symbol: str, qty: float) -> float:
    """심볼별 step_size 기준 수량 절삭"""
    try:
        step_size = get_symbol_precision(symbol)["step_size"]
        rounded_qty = float(Decimal(str(qty)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN))
        return rounded_qty if rounded_qty >= step_size else 0.0
    except Exception as e:
        logging.error(f"[오류] 수량 반올림 실패({symbol}): {e}")
        return 0.0


def round_price(symbol: str, price: float) -> float:
    """심볼별 tick_size 기준 가격 절삭"""
    try:
        tick_size = get_symbol_precision(symbol)["tick_size"]
        return float(Decimal(str(price)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN))
    except Exception as e:
        logging.error(f"[오류] 가격 반올림 실패({symbol}): {e}")
        return price


def calculate_order_quantity(symbol: str, entry_price: float, balance: float) -> float:
    try:
        precision = get_symbol_precision(symbol)
        step_size = precision["step_size"]

        capital = balance * CAPITAL_USAGE
        raw_qty = (capital * LEVERAGE) / entry_price
        quantity = round_quantity(symbol, raw_qty)
        notional = quantity * entry_price

        logging.debug(f"[디버그] {symbol} 수량 계산 → 잔고: {balance:.2f}, 사용금액: {capital:.2f}, "
                      f"진입가: {entry_price:.4f}, raw_qty: {raw_qty:.6f}, 절삭수량: {quantity}, notional: {notional:.4f}")

        # ✅ 최소 수량보다 작으면 실패
        if quantity < step_size:
            logging.warning(f"[경고] {symbol} 수량 {quantity} < 최소 단위 {step_size}")
            return 0.0

        # ✅ 최소 금액 미만 시 → 한 단계 올려서 재시도
        if notional < MIN_NOTIONAL:
            adjusted_qty = round_quantity(symbol, quantity + step_size)
            adjusted_notional = adjusted_qty * entry_price
            if adjusted_notional >= MIN_NOTIONAL:
                logging.info(f"[보정] {symbol} 수량 보정: {quantity} → {adjusted_qty}")
                return adjusted_qty
            else:
                logging.warning(f"[경고] {symbol} 주문 금액 {notional:.4f} USDT < 최소 {MIN_NOTIONAL} USDT")
                return 0.0

        return quantity

    except Exception as e:
        logging.error(f"[오류] {symbol} 수량 계산 실패: {e}")
        return 0.0



def apply_slippage(price: float, side: str) -> float:
    """롱/숏 방향에 따라 슬리피지 반영"""
    try:
        if side.upper() == "LONG":
            return round(price * (1 + SLIPPAGE), 4)
        elif side.upper() == "SHORT":
            return round(price * (1 - SLIPPAGE), 4)
    except Exception as e:
        logging.error(f"[오류] 슬리피지 계산 실패: {e}")
    return round(price, 4)


def to_kst(dt):
    """UTC → KST 변환"""
    try:
        return dt + timedelta(hours=9)
    except Exception as e:
        logging.error(f"[오류] KST 변환 실패: {e}")
        return dt


def calculate_rsi(prices: list, period: int = 14) -> float:
    """RSI 계산 (기본 14)"""
    try:
        import numpy as np
        if len(prices) < period:
            return 50.0
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed > 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        return 100 - 100 / (1 + rs)
    except Exception as e:
        logging.error(f"[오류] RSI 계산 실패: {e}")
        return 50.0


def cancel_all_orders(symbol: str) -> None:
    """해당 심볼의 모든 미체결 주문 취소 (조용히 처리)"""
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
    except Exception as e:
        logging.error(f"[오류] {symbol} 주문 정리 실패: {e}")
