# 파일명: order_manager.py
# 중앙 주문 처리 모듈
# core.py에 정의된 함수·클래스를 활용하여
# 지정가 진입 → 체결 확인 → TP/SL 설정 → 포지션 등록 과정을 수행합니다.
import logging
import time
from binance_client import client, cancel_all_orders_for_symbol
from core import (
    create_limit_order,
    place_market_order,
    place_market_exit,
    get_price,
    create_take_profit,
    create_stop_order,
    calculate_order_quantity,
    log_trade,
    summarize_trades,
    can_enter,
    add_position,
    remove_position,
    send_telegram
)

# binance_client.py

def cancel_exit_orders_for_symbol(symbol: str):
    """
    지정 심볼의 모든 청산용 TP/SL 주문을 삭제합니다.
    포지션이 없는 경우에도 해당 주문은 남아 있을 수 있습니다.
    """
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            if order["reduceOnly"]:  # 청산용 주문만 선택
                client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                logging.info(f"[청산 주문 삭제] {symbol} 주문 ID: {order['orderId']}")
    except Exception as e:
        logging.error(f"[청산 주문 삭제 오류] {symbol}: {e}")


from decimal import Decimal

def handle_entry(signal: dict) -> None:
    """
    signal 구조:
      {
        'symbol': str,
        'side': 'BUY' or 'SELL',
        'direction': 'long' or 'short',
        'strategy': str,
        'qty': float,
        'tp_percent': float,
        'sl_percent': float
      }
    """
    symbol = signal['symbol']
    side = signal['side']
    direction = signal['direction']
    strategy = signal['strategy']
    qty = signal['qty']
    tp_percent = signal['tp_percent']
    sl_percent = signal['sl_percent']

    # 중복 진입 방지
    if not can_enter(symbol, strategy):
        return

    # 1) 지정가 진입 주문
    price = get_price(symbol)
    entry_order = create_limit_order(symbol, side, qty, price)
    if not entry_order or entry_order.get('orderId') is None:
        send_telegram(f"⚠️ [{strategy.upper()}] {symbol} 지정가 주문 실패")
        return

    order_id = entry_order['orderId']
    # 2) 체결 대기
    time.sleep(1)

    # 3) 체결 확인
    try:
        order_info = client.futures_get_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        send_telegram(f"⚠️ [{strategy.upper()}] {symbol} 주문 확인 오류: {e}")
        cancel_all_orders_for_symbol(symbol)
        return

    if order_info.get('status') != 'FILLED':
        send_telegram(f"⚠️ [{strategy.upper()}] {symbol} 미체결, 주문 취소")
        cancel_all_orders_for_symbol(symbol)
        return

    # 체결가 추출
    entry_price = float(order_info.get('avgFillPrice', order_info.get('price', price)))

    # 4) TP/SL 설정
    if direction == 'long':
        tp = float(Decimal(str(entry_price)) * (Decimal("1") + Decimal(str(tp_percent)) / Decimal("100")))

        sl = float(Decimal(str(entry_price)) * (Decimal("1") - Decimal(str(sl_percent)) / Decimal("100")))
    else:
        tp = float(Decimal(str(entry_price)) * (Decimal("1") - Decimal(str(tp_percent)) / Decimal("100")))
        sl = float(Decimal(str(entry_price)) * (Decimal("1") + Decimal(str(sl_percent)) / Decimal("100")))

    tp_order = create_take_profit(symbol, 'SELL' if direction == 'long' else 'BUY', tp)
    sl_order = create_stop_order(symbol, 'SELL' if direction == 'long' else 'BUY', sl)

    if not tp_order or not sl_order:
        send_telegram(f"⚠️ [{strategy.upper()}] {symbol} TP/SL 설정 실패, 진입 무효 처리")
        cancel_all_orders_for_symbol(symbol)
        return

    # 5) 포지션 등록 및 로그
    add_position(symbol, direction, entry_price, qty, strategy)
    log_trade({
        'symbol': symbol,
        'strategy': strategy,
        'side': direction,
        'entry_price': entry_price,
        'tp': tp,
        'sl': sl,
        'position_size': qty,
        'status': 'entry'
    })
    send_telegram(
        f"✅ [{strategy.upper()}] {symbol} 진입 성공 @ {entry_price:.4f}\n"
        f"TP: {tp:.4f} / SL: {sl:.4f} | Qty: {qty}"
    )


def handle_exit(symbol: str, strategy: str, direction: str, qty: float, entry_price: float, reason: str) -> None:
    """
    포지션 청산 처리
    """
    # 현재가 조회
    price = get_price(symbol)
    if price is None:
        return

    # 시장가 청산
    place_market_exit(symbol, 'SELL' if direction == 'long' else 'BUY', qty)
    remove_position(symbol)

    # 손익 계산
    if direction == 'long':
        pl = (price - entry_price) * qty
    else:
        pl = (entry_price - price) * qty

    # 로그 및 알림
    log_trade({
        'symbol': symbol,
        'strategy': strategy,
        'side': direction,
        'exit_price': price,
        'entry_price': entry_price,
        'reason': reason,
        'position_size': qty,
        'status': 'exit'
    })
    emoji = '🟢' if pl >= 0 else '🔴'
    send_telegram(f"{emoji} [{strategy.upper()}] {symbol} 청산 @ {price:.4f} | 손익: {pl:.2f} USDT")
    send_telegram(summarize_trades())
