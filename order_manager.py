# order_manager.py

import logging
import time
from decimal import Decimal, ROUND_DOWN, getcontext

from binance_client import client, change_leverage
from telegram_bot import send_message
from position_manager import add_position, remove_position
from risk_config import get_leverage

# 소수점 처리 정밀도 설정
getcontext().prec = 18
ORDER_TIMEOUT_SEC = 30  # 주문 체결 대기 최대 시간 (초)

def place_limit_order(symbol: str, side: str, quantity: Decimal, price: Decimal) -> dict:
    """
    지정가 주문을 걸고, 최대 ORDER_TIMEOUT_SEC 동안 체결을 확인합니다.
    체결되지 않으면 주문을 취소하고 빈 dict를 반환합니다.
    """
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            timeInForce='GTC',
            quantity=str(quantity.quantize(Decimal('1e-8'), rounding=ROUND_DOWN)),
            price=str(price)
        )
        order_id = order['orderId']
    except Exception as e:
        logging.error(f"[주문 오류] {symbol} {side} {quantity}@{price}: {e}")
        return {}

    start = time.time()
    while time.time() - start < ORDER_TIMEOUT_SEC:
        try:
            status = client.futures_get_order(symbol=symbol, orderId=order_id)['status']
            if status == 'FILLED':
                return order
        except Exception as e:
            logging.error(f"[체결 확인 오류] {symbol} 주문 {order_id}: {e}")
        time.sleep(0.5)

    # 체결 실패 시 주문 취소
    try:
        client.futures_cancel_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        logging.error(f"[주문 취소 오류] {symbol} 주문 {order_id}: {e}")
    return {}

def set_oco_orders(symbol: str, side: str,
                   tp_price: Decimal, sl_price: Decimal):
    """
    TP/SL Market 주문(Stop Market + Take Profit Market) 설정.
    한쪽 체결 시 반대쪽은 자동 취소됩니다.
    """
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    try:
        # 손절 Stop Market
        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type='STOP_MARKET',
            stopPrice=str(sl_price),
            closePosition=True
        )
        # 익절 Take Profit Market
        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=str(tp_price),
            closePosition=True
        )
    except Exception as e:
        logging.error(f"[OCO 설정 오류] {symbol} TP:{tp_price} SL:{sl_price}: {e}")

def handle_entry(symbol: str,
                 side: str,
                 quantity: Decimal,
                 entry_price: Decimal,
                 sl_price: Decimal,
                 tp_price: Decimal,
                 strategy_name: str):
    """
    전략 진입 처리:
      1) 레버리지 설정
      2) 지정가 주문 → 체결 확인
      3) 포지션 메모리 등록
      4) TP/SL 설정
      5) 텔레그램 알림
    """
    # 1) 레버리지 조정
    lev = get_leverage(strategy_name)
    change_leverage(symbol, lev)

    # 2) 지정가 진입 주문
    order = place_limit_order(symbol, side, quantity, entry_price)
    if not order:
        send_message(f"⚠️ {strategy_name} {symbol} 진입 실패")
        return

    # 3) 메모리 등록
    add_position({
        'symbol': symbol,
        'side': side,
        'quantity': str(quantity),
        'entry_price': str(entry_price),
        'sl_price': str(sl_price),
        'tp_price': str(tp_price),
        'strategy': strategy_name,
        'entry_time': time.strftime("%Y-%m-%d %H:%M:%S")
    })

    # 4) TP/SL OCO 주문
    set_oco_orders(symbol, side, tp_price, sl_price)

    # 5) 진입 알림
    send_message(f"✅ {strategy_name} {symbol} 진입: {side} {quantity}@{entry_price}")

def handle_exit(position: dict, reason: str):
    """
    전략 청산 처리:
      1) 시장가 청산 주문
      2) 포지션 메모리 제거
      3) 텔레그램 알림
    """
    symbol = position['symbol']
    side = 'SELL' if position['side'] == 'BUY' else 'BUY'
    qty = Decimal(position['quantity']).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)

    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=str(qty)
        )
    except Exception as e:
        logging.error(f"[청산 오류] {symbol} {reason}: {e}")
        send_message(f"⚠️ 청산 실패 {symbol}: {e}")
        return

    # 메모리에서 제거
    remove_position(position)

    # 청산 알림
    send_message(f"❌ {position['strategy']} {symbol} 청산({reason})")
