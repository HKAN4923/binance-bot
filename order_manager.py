"""주문 실행 및 감시 모듈"""

import logging
from datetime import datetime
from typing import Any, Dict, List

import position_manager
import trade_summary
import utils
from binance_client import client
from risk_config import (
    USE_MARKET_TP_SL,
    USE_MARKET_TP_SL_BACKUP,
    TP_SL_SLIPPAGE_RATE,
    LEVERAGE,
)

POSITIONS_TO_MONITOR: List[Dict[str, Any]] = []


def get_current_price(symbol: str) -> float:
    """현재가 조회"""
    ticker = client.futures_symbol_ticker(symbol=symbol)
    return float(ticker["price"])


def place_entry_order(symbol: str, side: str, strategy_name: str) -> Dict[str, Any]:
    """시장가 진입 주문 (실전)"""
    try:
        entry_price = get_current_price(symbol)

        # ✅ 레버리지 자동 설정
        try:
            client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        except Exception as e:
            logging.warning(f"[레버리지 설정 실패] {symbol}: {e}")

        qty = utils.calculate_order_quantity(symbol, entry_price)
        side_binance = "BUY" if side.upper() == "LONG" else "SELL"

        order = client.futures_create_order(
            symbol=symbol,
            side=side_binance,
            type="MARKET",
            quantity=qty,
        )

        fills = order.get("fills", [])
        filled_price = float(fills[0]["price"]) if fills else entry_price

        position = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": filled_price,
            "strategy": strategy_name,
            "entry_time": datetime.utcnow().isoformat(),
        }

        logging.info(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 "
                     f"(수량: {qty}, 체결가: {filled_price})")

        if not USE_MARKET_TP_SL:
            success = place_tp_sl_orders(symbol, side, filled_price, qty)
            if not success and USE_MARKET_TP_SL_BACKUP:
                POSITIONS_TO_MONITOR.append(position)
                logging.warning(f"[백업] 지정가 TP/SL 실패 → {symbol} 감시 목록 등록됨")
                position_manager.add_position(position)
        else:
            POSITIONS_TO_MONITOR.append(position)
            position_manager.add_position(position)

        return position

    except Exception as e:
        logging.error(f"[오류] 진입 주문 실패: {e}")
        return {}


def place_tp_sl_orders(symbol: str, side: str, entry_price: float, qty: float) -> bool:
    """지정가 TP/SL 주문"""
    try:
        tp_price = utils.apply_slippage(entry_price, side, TP_SL_SLIPPAGE_RATE)
        sl_price = utils.apply_slippage(entry_price, side, -TP_SL_SLIPPAGE_RATE)

        side_tp = "SELL" if side.upper() == "LONG" else "BUY"
        side_sl = side_tp

        # TP
        client.futures_create_order(
            symbol=symbol,
            side=side_tp,
            type="TAKE_PROFIT_MARKET",
            stopPrice=round(tp_price, 2),
            closePosition=True,
            timeInForce="GTC"
        )

        # SL
        client.futures_create_order(
            symbol=symbol,
            side=side_sl,
            type="STOP_MARKET",
            stopPrice=round(sl_price, 2),
            closePosition=True,
            timeInForce="GTC"
        )

        logging.info(f"[TP/SL 설정] {symbol} TP: {tp_price:.2f}, SL: {sl_price:.2f}")
        return True

    except Exception as e:
        logging.error(f"[오류] TP/SL 지정가 주문 실패: {e}")
        return False


def monitor_positions() -> None:
    """포지션 감시 (시장가 TP/SL 감시 청산)"""
    closed = []

    for pos in POSITIONS_TO_MONITOR:
        try:
            current = get_current_price(pos["symbol"])
            tp = utils.apply_slippage(pos["entry_price"], pos["side"], TP_SL_SLIPPAGE_RATE)
            sl = utils.apply_slippage(pos["entry_price"], pos["side"], -TP_SL_SLIPPAGE_RATE)

            if pos["side"] == "LONG":
                if current >= tp:
                    pos["pnl"] = (tp - pos["entry_price"]) * pos["qty"]
                    logging.info(f"[청산] {pos['symbol']} TP 도달")
                    closed.append(pos)
                elif current <= sl:
                    pos["pnl"] = (sl - pos["entry_price"]) * pos["qty"]
                    logging.info(f"[청산] {pos['symbol']} SL 도달")
                    closed.append(pos)
            else:
                if current <= tp:
                    pos["pnl"] = (pos["entry_price"] - tp) * pos["qty"]
                    logging.info(f"[청산] {pos['symbol']} TP 도달")
                    closed.append(pos)
                elif current >= sl:
                    pos["pnl"] = (pos["entry_price"] - sl) * pos["qty"]
                    logging.info(f"[청산] {pos['symbol']} SL 도달")
                    closed.append(pos)

        except Exception as e:
            logging.error(f"[감시 오류] {pos['symbol']} 감시 실패: {e}")

    for pos in closed:
        POSITIONS_TO_MONITOR.remove(pos)
        position_manager.remove_position(pos)
        trade_summary.add_trade_entry(pos)


def force_market_exit(position: Dict[str, Any]) -> None:
    """시장가 강제 청산"""
    try:
        side = "SELL" if position["side"] == "LONG" else "BUY"
        client.futures_create_order(
            symbol=position["symbol"],
            side=side,
            type="MARKET",
            quantity=position["qty"]
        )
        logging.warning(f"[강제 청산] {position['symbol']} 포지션 시장가 종료")

    except Exception as e:
        logging.error(f"[강제 청산 실패] {e}")

    if position in POSITIONS_TO_MONITOR:
        POSITIONS_TO_MONITOR.remove(position)
    position_manager.remove_position(position)
    trade_summary.add_trade_entry(position)
