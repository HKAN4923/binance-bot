# strategy_pullback.py
"""
Pullback 전략 (롱 진입 전용)
– EMA21 크로스 기반 진입
– TP/SL 및 타임컷 조건으로 청산
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd

from binance_client import get_ohlcv, get_price
from position_manager import can_enter, get_positions
from order_manager import handle_entry, handle_exit
from risk_config import (
    PULLBACK_TP_PERCENT,
    PULLBACK_SL_PERCENT,
    PULLBACK_TIMECUT_HOURS,
)
from utils import calculate_order_quantity

def check_entry(symbol: str) -> None:
    """
    Pullback 전략 진입 체크:
      1) 최대 포지션 미만
      2) 동일 심볼 중복 진입 방지
      3) 5m 봉 EMA21 크로스(이전 종가 < EMA21, 현재 종가 > EMA21) 시 롱 진입
    """
    if not can_enter():
        return
    # 중복 진입 방지
    for pos in get_positions():
        if pos.get("symbol") == symbol and pos.get("strategy") == "Pullback":
            return

    df = get_ohlcv(symbol, interval="5m", limit=30)
    if df is None or len(df) < 22:
        return

    # EMA21 계산
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    prev, curr = df.iloc[-2], df.iloc[-1]
    # EMA21 크로스 확인
    if not (prev["close"] < prev["ema21"] and curr["close"] > curr["ema21"]):
        return

    # 수량 계산
    raw_qty = calculate_order_quantity(symbol)
    if raw_qty <= 0:
        return
    qty = Decimal(str(raw_qty))

    # 진입가·TP·SL 가격 정의
    price    = Decimal(str(get_price(symbol)))
    tp_price = (price * (Decimal("1") + PULLBACK_TP_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))
    sl_price = (price * (Decimal("1") - PULLBACK_SL_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))

    # 진입 처리
    handle_entry(
        symbol=symbol,
        side="BUY",
        quantity=qty,
        entry_price=price,
        sl_price=sl_price,
        tp_price=tp_price,
        strategy_name="Pullback",
    )

def check_exit(symbol: str) -> None:
    """
    Pullback 전략 청산 체크:
      – TP/SL 도달
      – 진입 후 타임컷 경과
    """
    now = datetime.utcnow()
    for pos in get_positions():
        if pos.get("symbol") != symbol or pos.get("strategy") != "Pullback":
            continue

        entry_time  = datetime.strptime(pos["entry_time"], "%Y-%m-%d %H:%M:%S")
        tp_price    = Decimal(pos["tp_price"])
        sl_price    = Decimal(pos["sl_price"])
        price       = Decimal(str(get_price(symbol)))
        reason      = None

        if price >= tp_price:
            reason = "TP"
        elif price <= sl_price:
            reason = "SL"
        elif now - entry_time >= timedelta(hours=PULLBACK_TIMECUT_HOURS):
            reason = "TimeCut"

        if reason:
            handle_exit(position=pos, reason=reason)
