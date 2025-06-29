import logging
from datetime import datetime
from binance.exceptions import BinanceAPIException

from binance_client import client
from risk_config import LEVERAGE, TP_SL_SETTINGS, TIME_CUT_BY_STRATEGY
from utils import calculate_order_quantity, round_price, round_quantity, get_futures_balance, cancel_all_orders
from telegram_bot import send_message
from position_manager import (
    add_position,
    remove_position,
    get_positions,
    is_duplicate,
    is_in_cooldown,
    load_positions as get_positions_from_log
)


def place_tp_sl_orders(symbol: str, side: str, entry_price: float, quantity: float, strategy_name: str):
    try:
        settings = TP_SL_SETTINGS.get(strategy_name.upper())
        tp_pct = settings["tp"]
        sl_pct = settings["sl"]

        tp_price = entry_price * (1 + tp_pct) if side == "BUY" else entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 - sl_pct) if side == "BUY" else entry_price * (1 + sl_pct)

        tp_price = round_price(symbol, tp_price)
        sl_price = round_price(symbol, sl_price)
        quantity = round_quantity(symbol, quantity)
        exit_side = "SELL" if side == "BUY" else "BUY"

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
        side = side.upper()
        if side == "LONG":
            side = "BUY"
        elif side == "SHORT":
            side = "SELL"

        if side not in ["BUY", "SELL"]:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 잘못된 side 값: {side}")
            return

        ticker = client.futures_symbol_ticker(symbol=symbol)
        entry_price = round_price(symbol, float(ticker['price']))

        if entry_price == 0:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 현재가 조회 실패")
            return

        balance = get_futures_balance()
        quantity = calculate_order_quantity(symbol, entry_price, balance)
        quantity = round_quantity(symbol, quantity)

        if quantity == 0:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 수량 계산 실패")
            return

        logging.info(f"[디버그] 진입 시도 - 심볼: {symbol}, 가격: {entry_price:.4f}, 수량: {quantity:.6f}")

        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)

        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )

        # ✅ 수정된 체결가 추출 방식
        fill_price = float(order.get("avgFillPrice") or order.get("avgPrice") or entry_price)

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

    except BinanceAPIException as e:
        logging.error(f"[오류] 진입 주문 실패(Binance): {e}")
    except Exception as e:
        logging.error(f"[오류] 진입 주문 실패: {e}")


def monitor_positions():
    try:
        open_positions = client.futures_position_information()
        tracked_positions = get_positions_from_log()

        for pos in open_positions:
            amt = float(pos["positionAmt"])
            if amt == 0:
                continue

            symbol = pos["symbol"]
            side = "BUY" if amt > 0 else "SELL"
            entry_side = "LONG" if amt > 0 else "SHORT"

            match = next((p for p in tracked_positions if p["symbol"] == symbol and p["side"] == side), None)
            if not match:
                logging.warning(f"[감시제외] {symbol} 전략정보 없음 (포지션은 존재함)")
                continue

            strategy = match["strategy"]
            entry_price = float(match["entry_price"])
            entry_time = datetime.fromisoformat(match["entry_time"])
            now = datetime.utcnow()

            # 현재가 조회
            ticker = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])

            # ✅ 감시 상태 출력
            elapsed_min = int((now - entry_time).total_seconds() / 60)
            logging.info(
                f"[감시중] {symbol} 전략: {strategy} | 진입가: {entry_price:.4f} | 현재가: {current_price:.4f} | 경과: {elapsed_min}분"
            )

            # 전략별 TP/SL 기준
            settings = TP_SL_SETTINGS.get(strategy.upper(), {})
            tp_pct = settings.get("tp", 0.02)
            sl_pct = settings.get("sl", 0.01)

            if side == "BUY":
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)
                is_tp_hit = current_price >= tp_price
                is_sl_hit = current_price <= sl_price
            else:
                tp_price = entry_price * (1 - tp_pct)
                sl_price = entry_price * (1 + sl_pct)
                is_tp_hit = current_price <= tp_price
                is_sl_hit = current_price >= sl_price

            # ✅ TP 청산
            if is_tp_hit:
                logging.info(f"[TP] {symbol} {strategy} TP 도달 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_message(f"[TP] {symbol} {strategy} TP 도달 → 시장가 청산")
                continue

            # ✅ SL 청산
            if is_sl_hit:
                logging.info(f"[SL] {symbol} {strategy} SL 도달 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_message(f"[SL] {symbol} {strategy} SL 도달 → 시장가 청산")
                continue

            # ✅ 신호 무효화 감지
            from strategy_orb import StrategyORB
            from strategy_nr7 import StrategyNR7
            from strategy_ema_cross import StrategyEMACross
            from strategy_holy_grail import StrategyHolyGrail

            strategy_map = {
                "ORB": StrategyORB([]),
                "NR7": StrategyNR7([]),
                "EMA": StrategyEMACross([]),
                "HOLY_GRAIL": StrategyHolyGrail([])
            }

            strat_obj = strategy_map.get(strategy.upper())
            if strat_obj and hasattr(strat_obj, "check_exit"):
                try:
                    if strat_obj.check_exit(symbol, entry_side):
                        logging.info(f"[무효화] {symbol} {strategy} 신호 반전 → 시장가 청산")
                        cancel_all_orders(symbol)
                        client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                                    type="MARKET", quantity=abs(amt), reduceOnly=True)
                        remove_position(symbol, strategy)
                        send_message(f"[무효화] {symbol} {strategy} 신호 반전으로 청산됨")
                        continue
                except Exception as e:
                    logging.error(f"[감시 오류] {symbol} {strategy} 신호판단 실패: {e}")

            # ✅ 시간 초과 청산
            max_minutes = TIME_CUT_BY_STRATEGY.get(strategy.upper(), 120)
            if (now - entry_time).total_seconds() > max_minutes * 60:
                logging.info(f"[타임컷] {symbol} 전략 {strategy} 시간 초과 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_message(f"[타임컷] {symbol} 전략 {strategy} 시간 초과로 청산됨")

    except Exception as e:
        logging.error(f"[감시 오류] 포지션 감시 중 오류 발생: {e}")