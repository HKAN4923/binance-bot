"""주문 실행 및 감시 모듈"""

import logging
from datetime import datetime
from typing import Any, Dict, List

import position_manager
import trade_summary
import utils
from risk_config import USE_MARKET_TP_SL, USE_MARKET_TP_SL_BACKUP, TP_SL_SLIPPAGE_RATE

POSITIONS_TO_MONITOR: List[Dict[str, Any]] = []


def place_entry_order(symbol: str, side: str, strategy_name: str) -> Dict[str, Any]:
    """시장가 진입 주문 실행"""
    entry_price = round(utils.apply_slippage(100.0, side, 0), 2)  # 시뮬레이션용 고정 가격
    qty = utils.calculate_order_quantity(symbol, entry_price)
    position = {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "strategy": strategy_name,
        "entry_time": datetime.utcnow().isoformat(),
    }

    logging.info(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 (수량: {qty}, 가격: {entry_price})")

    # 지정가 TP/SL 시도
    if not USE_MARKET_TP_SL:
        success = place_tp_sl_orders(symbol, side, entry_price)
        if not success and USE_MARKET_TP_SL_BACKUP:
            POSITIONS_TO_MONITOR.append(position)
            logging.warning(f"[백업] 지정가 TP/SL 실패 → {symbol} 감시 목록에 등록됨")
            position_manager.add_position(position)
    else:
        POSITIONS_TO_MONITOR.append(position)
        position_manager.add_position(position)

    return position


def place_tp_sl_orders(symbol: str, side: str, entry_price: float) -> bool:
    """지정가 TP/SL 주문 시뮬레이션"""
    try:
        tp_price = utils.apply_slippage(entry_price, side, TP_SL_SLIPPAGE_RATE)
        sl_price = utils.apply_slippage(entry_price, side, -TP_SL_SLIPPAGE_RATE)

        logging.info(f"[TP/SL 설정] {symbol} TP: {tp_price:.2f}, SL: {sl_price:.2f} (지정가 시도)")
        # 여기선 주문 등록 없이 성공했다고 가정
        return True

    except Exception as e:
        logging.error(f"[오류] TP/SL 지정가 등록 실패: {e}")
        return False


def monitor_positions() -> None:
    """포지션 감시 루프 (시장가 TP/SL 감시 청산)"""
    closed = []

    for pos in POSITIONS_TO_MONITOR:
        price = pos["entry_price"]  # 실제로는 현재가를 실시간 조회해야 함
        tp_price = utils.apply_slippage(price, pos["side"], TP_SL_SLIPPAGE_RATE)
        sl_price = utils.apply_slippage(price, pos["side"], -TP_SL_SLIPPAGE_RATE)

        if pos["side"] == "LONG":
            if price >= tp_price:
                logging.info(f"[청산] {pos['symbol']} TP 도달")
                pos["pnl"] = (tp_price - pos["entry_price"]) * pos["qty"]
                closed.append(pos)
            elif price <= sl_price:
                logging.info(f"[청산] {pos['symbol']} SL 도달")
                pos["pnl"] = (sl_price - pos["entry_price"]) * pos["qty"]
                closed.append(pos)

        if pos["side"] == "SHORT":
            if price <= tp_price:
                logging.info(f"[청산] {pos['symbol']} TP 도달")
                pos["pnl"] = (pos["entry_price"] - tp_price) * pos["qty"]
                closed.append(pos)
            elif price >= sl_price:
                logging.info(f"[청산] {pos['symbol']} SL 도달")
                pos["pnl"] = (pos["entry_price"] - sl_price) * pos["qty"]
                closed.append(pos)

    for pos in closed:
        POSITIONS_TO_MONITOR.remove(pos)
        position_manager.remove_position(pos)
        trade_summary.add_trade_entry(pos)


def force_market_exit(position: Dict[str, Any]) -> None:
    """시장가 강제 청산 (타임컷 등)"""
    logging.warning(f"[강제 청산] {position['symbol']} 포지션 종료됨")
    if position in POSITIONS_TO_MONITOR:
        POSITIONS_TO_MONITOR.remove(position)
    position_manager.remove_position(position)
    trade_summary.add_trade_entry(position)
