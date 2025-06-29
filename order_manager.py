import logging
from datetime import datetime, timedelta
from binance.exceptions import BinanceAPIException

from binance_client import client
from risk_config import LEVERAGE, TIME_CUT_BY_STRATEGY, TP_SL_SETTINGS
from utils import calculate_order_quantity, round_price
from telegram_bot import send_message
from position_manager import (
    add_position,
    remove_position,
    get_positions,
    get_position_info,
    cancel_all_orders
)

POSITIONS_TO_MONITOR = []

def get_current_price(symbol: str) -> float:
    try:
        ticker = client.futures_ticker_price(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        logging.error(f"[오류] 현재가 조회 실패: {e}")
        return 0.0

def place_tp_sl_orders(symbol: str, side: str, entry_price: float, quantity: float, strategy_name: str):
    try:
        settings = TP_SL_SETTINGS.get(strategy_name.upper(), {"tp": 0.02, "sl": 0.01})
        tp_pct = settings["tp"]
        sl_pct = settings["sl"]

        tp_price = entry_price * (1 + tp_pct) if side.upper() == "BUY" else entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 - sl_pct) if side.upper() == "BUY" else entry_price * (1 + sl_pct)

        tp_price = round_price(symbol, tp_price)
        sl_price = round_price(symbol, sl_price)
        exit_side = "SELL" if side.upper() == "BUY" else "BUY"

        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type="LIMIT",
            price=tp_price,
            quantity=quantity,
            timeInForce="GTC",
            reduceOnly=True
        )
        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type="STOP_MARKET",
            stopPrice=sl_price,
            quantity=quantity,
            timeInForce="GTE_GTC",
            reduceOnly=True
        )
        return True, True

    except BinanceAPIException as e:
        logging.error(f"[오류] TP/SL 지정가 주문 실패: {e}")
        return False, False
    except Exception as e:
        logging.error(f"[오류] TP/SL 주문 실패: {e}")
        return False, False

def place_entry_order(symbol: str, side: str, strategy_name: str) -> None:
    try:
        entry_price = get_current_price(symbol)
        if entry_price == 0:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 현재가 조회 실패")
            return

        balance = float(client.futures_account_balance()[0]['balance'])
        quantity = calculate_order_quantity(symbol, entry_price, balance)

        if quantity == 0:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 수량 계산 실패")
            return

        logging.info(f"[디버그] 진입 시도 - 심볼: {symbol}, 가격: {entry_price:.4f}, 수량: {quantity:.6f}")

        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)

        order = client.futures_create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=quantity
        )

        fill_price = float(order['fills'][0]['price'])

        logging.info(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 (수량: {quantity}, 체결가: {fill_price})")
        send_message(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 (수량: {quantity}, 체결가: {fill_price})")

        place_tp_sl_orders(symbol, side, fill_price, quantity, strategy_name)

        position_data = {
            "symbol": symbol,
            "strategy": strategy_name,
            "side": side,
            "entry_price": fill_price,
            "entry_time": datetime.utcnow().isoformat()
        }
        add_position(position_data)
        POSITIONS_TO_MONITOR.append(position_data)

    except BinanceAPIException as e:
        logging.error(f"[오류] 진입 주문 실패(Binance): {e}")
    except Exception as e:
        logging.error(f"[오류] 진입 주문 실패: {e}")

def monitor_positions(strategies) -> None:
    now = datetime.utcnow()

    if POSITIONS_TO_MONITOR:
        logging.info(f"[감시중] 현재 감시 중인 포지션 수: {len(POSITIONS_TO_MONITOR)}")
        for p in POSITIONS_TO_MONITOR:
            logging.info(f"[감시포지션] {p['symbol']} | 전략: {p['strategy']} | 방향: {p['side']} | 진입가: {p['entry_price']}")
    else:
        logging.info("[감시중] 현재 감시 중인 포지션 없음")

    closed = []
    for pos in POSITIONS_TO_MONITOR:
        symbol = pos["symbol"]
        strat_name = pos["strategy"]
        entry_price = pos["entry_price"]
        side = pos["side"]
        entry_time = datetime.fromisoformat(pos["entry_time"])

        try:
            strat = next(s for s in strategies if s.name == strat_name)
        except StopIteration:
            logging.warning(f"[경고] 감시 중 전략 {strat_name} 없음")
            continue

        cut_minutes = TIME_CUT_BY_STRATEGY.get(strat_name.upper(), 120)
        elapsed = now - entry_time
        if elapsed > timedelta(minutes=cut_minutes):
            logging.warning(f"[타임컷] {symbol} {cut_minutes}분 초과로 청산")
            close_position(symbol, side)
            closed.append(pos)
            continue

        settings = TP_SL_SETTINGS.get(strat_name.upper(), {"tp": 0.02, "sl": 0.01})
        tp_pct = settings["tp"]
        sl_pct = settings["sl"]
        tp_price = entry_price * (1 + tp_pct) if side.upper() == "BUY" else entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 - sl_pct) if side.upper() == "BUY" else entry_price * (1 + sl_pct)

        current_price = get_current_price(symbol)

        if side.upper() == "BUY" and current_price >= tp_price:
            logging.warning(f"[익절청산] {symbol} 현재가 {current_price:.4f} >= TP {tp_price:.4f}")
            close_position(symbol, side)
            closed.append(pos)
            continue
        elif side.upper() == "BUY" and current_price <= sl_price:
            logging.warning(f"[손절청산] {symbol} 현재가 {current_price:.4f} <= SL {sl_price:.4f}")
            close_position(symbol, side)
            closed.append(pos)
            continue
        elif side.upper() == "SELL" and current_price <= tp_price:
            logging.warning(f"[익절청산] {symbol} 현재가 {current_price:.4f} <= TP {tp_price:.4f}")
            close_position(symbol, side)
            closed.append(pos)
            continue
        elif side.upper() == "SELL" and current_price >= sl_price:
            logging.warning(f"[손절청산] {symbol} 현재가 {current_price:.4f} >= SL {sl_price:.4f}")
            close_position(symbol, side)
            closed.append(pos)
            continue

        try:
            if hasattr(strat, "check_exit") and strat.check_exit(symbol, entry_price, side):
                logging.warning(f"[신호 무효화] {symbol} → 조건 반전으로 청산")
                close_position(symbol, side)
                closed.append(pos)
        except Exception as e:
            logging.error(f"[오류] {symbol} 조건 확인 중 오류: {e}")

    for c in closed:
        remove_position(c["symbol"], c["strategy"])
        POSITIONS_TO_MONITOR.remove(c)

def close_position(symbol: str, side: str) -> None:
    try:
        opposite = "SELL" if side.upper() == "BUY" else "BUY"

        pos_info = get_position_info(symbol)
        qty = abs(float(pos_info["positionAmt"]))
        if qty == 0:
            logging.info(f"[청산 스킵] {symbol} 포지션 없음 → 주문 정리만 진행")
            cancel_all_orders(symbol)
            return

        client.futures_create_order(
            symbol=symbol,
            side=opposite,
            type="MARKET",
            quantity=qty
        )
        logging.info(f"[청산] {symbol} 포지션 시장가 청산 완료")
        send_message(f"[청산] {symbol} 시장가 청산 완료 (수량: {qty})")
        cancel_all_orders(symbol)

    except BinanceAPIException as e:
        logging.error(f"[오류] {symbol} 청산 실패(Binance): {e}")
    except Exception as e:
        logging.error(f"[오류] {symbol} 청산 실패: {e}")
