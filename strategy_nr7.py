# strategy_nr7.py
# 라쉬케 전략: NR7 (Natural Range 7)
# 1h 봉 기준 narrow range 7 돌파 시 진입, TP/SL 및 시간 경과 조건으로 청산

from datetime import datetime, timedelta
from decimal import Decimal
from binance_client import get_ohlcv, get_price
from position_manager import can_enter, get_positions
from order_manager import handle_entry, handle_exit
from risk_config import NR7_TP_PERCENT, NR7_SL_PERCENT, NR7_TIMECUT_HOURS  # :contentReference[oaicite:0]{index=0}

def is_entry_time_kst() -> bool:
    """KST 09:00~09:59, 21:00~21:59에만 진입 조건 체크"""
    now = datetime.utcnow() + timedelta(hours=9)
    return (now.hour == 9 and now.minute < 60) or (now.hour == 21 and now.minute < 60)

def check_entry(symbol: str) -> None:
    """NR7 진입 조건 검사"""
    if not is_entry_time_kst() or not can_enter():
        return

    # 동일 심볼 중복 진입 방지
    for pos in get_positions():
        if pos.get("symbol") == symbol:
            return

    # 최근 8개 1h 봉 조회 (마지막은 현재 진행 중)
    df = get_ohlcv(symbol, interval="1h", limit=8)
    if df is None or len(df) < 8:
        return

    bars = df.iloc[:-1]  # 마지막 봉 제외
    # 변동폭 계산 및 가장 좁은 봉 선택
    ranges = (bars["high"] - bars["low"])
    idx = ranges.idxmin()
    narrow_high = Decimal(str(bars.loc[idx, "high"]))
    narrow_low  = Decimal(str(bars.loc[idx, "low"]))

    price = Decimal(str(get_price(symbol)))
    # 돌파 시그널 판단
    if price > narrow_high:
        side, direction = "BUY", "long"
    elif price < narrow_low:
        side, direction = "SELL", "short"
    else:
        return

    # 수량 계산 (utils.calculate_order_quantity를 이후 구현)
    # 예시 placeholder: qty = Decimal("0.0")
    from utils import calculate_order_quantity
    raw_qty = calculate_order_quantity(symbol)
    if raw_qty <= 0:
        return
    qty = Decimal(str(raw_qty))

    # TP/SL 가격 계산
    tp_price = (price * (Decimal("1") + NR7_TP_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))
    sl_price = (price * (Decimal("1") - NR7_SL_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))

    # 진입 처리
    handle_entry(
        symbol=symbol,
        side=side,
        quantity=qty,
        entry_price=price,
        sl_price=sl_price,
        tp_price=tp_price,
        strategy_name="NR7"
    )

def check_exit(symbol: str) -> None:
    """NR7 청산 조건 검사"""
    now = datetime.utcnow()
    for pos in get_positions():
        if pos.get("symbol") != symbol or pos.get("strategy") != "NR7":
            continue

        entry_time = datetime.strptime(pos["entry_time"], "%Y-%m-%d %H:%M:%S")
        entry_price = Decimal(pos["entry_price"])
        tp_price    = Decimal(pos["tp_price"])
        sl_price    = Decimal(pos["sl_price"])

        price = Decimal(str(get_price(symbol)))
        reason = None

        if price >= tp_price:
            reason = "TP"
        elif price <= sl_price:
            reason = "SL"
        elif now - entry_time >= timedelta(hours=NR7_TIMECUT_HOURS):
            reason = "TimeCut"

        if reason:
            handle_exit(position=pos, reason=reason)
