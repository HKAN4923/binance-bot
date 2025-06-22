# ✅ order_manager.py (수정된 버전)

import logging
import time
from decimal import Decimal, ROUND_DOWN, getcontext

from binance_client import client, cancel_exit_orders_for_symbol
from telegram_bot import send_message
from position_manager import add_position, remove_position
from risk_config import get_leverage
from trade_summary import record_trade
from binance_client import get_price

getcontext().prec = 18
ORDER_TIMEOUT_SEC = 30

def place_limit_order(symbol: str, side: str, quantity: Decimal, price: Decimal) -> dict:
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

    try:
        client.futures_cancel_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        logging.error(f"[주문 취소 오류] {symbol} 주문 {order_id}: {e}")
    return {}

def set_oco_orders(symbol: str, side: str,
                   tp_price: Decimal, sl_price: Decimal):
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    try:
        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type='STOP_MARKET',
            stopPrice=str(sl_price),
            closePosition=True
        )
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
    lev = get_leverage(strategy_name)
    try:
        client.futures_change_leverage(symbol=symbol, leverage=lev)
    except Exception as e:
        logging.warning(f"[레버리지 설정 실패] {symbol}: {e}")

    order = place_limit_order(symbol, side, quantity, entry_price)
    if not order:
        send_message(f"⚠️ {strategy_name} {symbol} 진입 실패")
        logging.warning(f"[진입 실패] {strategy_name} {symbol} {side} {quantity}@{entry_price}")
        return

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

    set_oco_orders(symbol, side, tp_price, sl_price)
    send_message(f"✅ {strategy_name} {symbol} 진입: {side} {quantity}@{entry_price}")
    logging.info(
        f"[진입] 전략={strategy_name}, 심볼={symbol}, 방향={side}, 수량={quantity}, "
        f"진입가={entry_price}, TP={tp_price}, SL={sl_price}, 레버리지={lev}"
    )

def handle_exit(position: dict, reason: str):
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

    # 실현 손익 기록 및 메시지 전송
    exit_price = str(get_price(symbol))
    pnl = record_trade(position, exit_price, reason)

    # TP/SL 주문 제거
    cancel_exit_orders_for_symbol(symbol)

    remove_position(position)
    send_message(f"❌ {position['strategy']} {symbol} 청산({reason}) / PnL: {pnl:.4f} USDT")
    logging.info(f"[청산] {position['strategy']} {symbol} 종료 ({reason}) → 손익: {pnl:.4f} USDT")
