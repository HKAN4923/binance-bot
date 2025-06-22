# strategy_orb.py

from datetime import datetime, timedelta
from decimal import Decimal
from binance_client import get_ohlcv, get_price
from position_manager import can_enter, get_positions
from order_manager import handle_entry, handle_exit
from risk_config import ORB_TP_PERCENT, ORB_SL_PERCENT, ORB_TIMECUT_HOURS

# 진입 가능 시간 (KST 기준 09:00~10:00, 21:00~22:00)
def is_entry_time_kst() -> bool:
    now = datetime.utcnow() + timedelta(hours=9)
    return (now.hour == 9 and now.minute < 60) or (now.hour == 21 and now.minute < 60)

def check_entry(symbol: str) -> None:
    """
    ORB 전략 진입 체크:
      - KST 09:00~09:59 또는 21:00~21:59에만 실행
      - 글로벌 최대 포지션 수 미만
      - 같은 심볼 기포지션 없을 때
      - 1시간 봉 직전 봉의 High 돌파 시 BUY 진입
    """
    if not is_entry_time_kst() or not can_enter():
        return

    # 같은 심볼 이미 진입했는지 확인
    for pos in get_positions():
        if pos.get("symbol") == symbol:
            return

    # 최근 두 개 1h 봉 조회
    df = get_ohlcv(symbol, interval="1h", limit=2)
    if df is None or len(df) < 2:
        return

    open_high = Decimal(str(df.iloc[-2]["high"]))
    open_low  = Decimal(str(df.iloc[-2]["low"]))
    price     = Decimal(str(get_price(symbol)))
    if price <= open_high:
        return  # 롱 돌파 아니면 무시

    # TP/SL 가격 계산 (퍼센트 기반)
    tp_price = (price * (Decimal("1") + ORB_TP_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))
    sl_price = (price * (Decimal("1") - ORB_SL_PERCENT / Decimal("100"))).quantize(Decimal("1e-8"))

    # 수량: order_manager 내부 체결·리스크 기준으로 계산
    qty = Decimal(str(price))  # placeholder; 실제는 utils.calculate_order_quantity 또는 risk_config 기반으로 계산
    # (예: qty = Decimal(str(calculate_order_quantity(symbol))))

    # 진입 처리
    handle_entry(
        symbol=symbol,
        side="BUY",
        quantity=qty,
        entry_price=price,
        sl_price=sl_price,
        tp_price=tp_price,
        strategy_name="ORB"
    )

def check_exit(symbol: str) -> None:
    """
    ORB 전략 청산 체크:
      - TP/SL 조건 만족 시
      - 진입 후 ORB_TIMECUT_HOURS 경과 시
    """
    now = datetime.utcnow()
    for pos in get_positions():
        if pos.get("symbol") != symbol or pos.get("strategy") != "ORB":
            continue

        # 저장된 문자열을 Decimal/Datetime 으로 변환
        entry_price = Decimal(pos["entry_price"])
        tp_price    = Decimal(pos["tp_price"])
        sl_price    = Decimal(pos["sl_price"])
        entry_time  = datetime.strptime(pos["entry_time"], "%Y-%m-%d %H:%M:%S")

        price = Decimal(str(get_price(symbol)))
        reason = None

        if price >= tp_price:
            reason = "TP"
        elif price <= sl_price:
            reason = "SL"
        elif now - entry_time >= timedelta(hours=ORB_TIMECUT_HOURS):
            reason = "TimeCut"

        if reason:
            handle_exit(position=pos, reason=reason)
