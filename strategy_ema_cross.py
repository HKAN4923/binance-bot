# strategy_ema_cross.py
"""
EMA 9/21 크로스 + RSI 필터 전략
- EMA_FAST_PERIOD, EMA_SLOW_PERIOD 기준 크로스 신호
- RSI 필터: 롱 진입 시 RSI ≥ EMA_RSI_LONG_MIN, 숏 진입 시 RSI ≤ EMA_RSI_SHORT_MAX
- TP/SL % 설정: EMA_TP_PERCENT, EMA_SL_PERCENT
- 시간 컷: EMA_TIMECUT_HOURS
"""

from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd

from binance_client import get_ohlcv, get_price
from position_manager import can_enter, get_positions
from order_manager import handle_entry, handle_exit
from risk_config import (
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    RSI_PERIOD,
    EMA_RSI_LONG_MIN,
    EMA_RSI_SHORT_MAX,
    EMA_TP_PERCENT,
    EMA_SL_PERCENT,
    EMA_TIMECUT_HOURS,
)

from utils import calculate_rsi, calculate_order_quantity

def check_entry(symbol: str) -> None:
    # 최대 포지션 수, 중복 진입 방지
    if not can_enter():
        return
    for pos in get_positions():
        if pos.get("symbol") == symbol and pos.get("strategy") == "EMA":
            return

    # 필요 데이터 수: EMA_SLOW_PERIOD, RSI_PERIOD 중 큰 값 + 2
    limit = max(EMA_SLOW_PERIOD, RSI_PERIOD) + 2
    df = get_ohlcv(symbol, interval="1h", limit=limit)
    if df is None or len(df) < limit:
        return

    # 지수이동평균 계산
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST_PERIOD, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW_PERIOD, adjust=False).mean()
    # RSI 계산
    df["rsi"] = calculate_rsi(df["close"], RSI_PERIOD)

    prev, curr = df.iloc[-2], df.iloc[-1]
    price = Decimal(str(get_price(symbol)))

    side = None
    # 골든크로스 + RSI 필터
    if prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"] and curr["rsi"] >= EMA_RSI_LONG_MIN:
        side = "BUY"
    # 데드크로스 + RSI 필터
    elif prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"] and curr["rsi"] <= EMA_RSI_SHORT_MAX:
        side = "SELL"
    else:
        return

    # TP/SL 가격 계산
    tp_price = (price * (Decimal("1") + EMA_TP_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))
    sl_price = (price * (Decimal("1") - EMA_SL_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))

    raw_qty = calculate_order_quantity(symbol)
    if raw_qty <= 0:
        return
    qty = Decimal(str(raw_qty))

    handle_entry(
        symbol=symbol,
        side=side,
        quantity=qty,
        entry_price=price,
        sl_price=sl_price,
        tp_price=tp_price,
        strategy_name="EMA",
    )


def check_exit(symbol: str) -> None:
    now = datetime.utcnow()
    for pos in get_positions():
        if pos.get("symbol") != symbol or pos.get("strategy") != "EMA":
            continue

        entry_time = datetime.strptime(pos["entry_time"], "%Y-%m-%d %H:%M:%S")
        tp_price    = Decimal(pos["tp_price"])
        sl_price    = Decimal(pos["sl_price"])
        price       = Decimal(str(get_price(symbol)))
        reason = None

        if price >= tp_price:
            reason = "TP"
        elif price <= sl_price:
            reason = "SL"
        elif now - entry_time >= timedelta(hours=EMA_TIMECUT_HOURS):
            reason = "TimeCut"

        if reason:
            handle_exit(position=pos, reason=reason)
