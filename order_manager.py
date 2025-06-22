"""주문 실행 및 감시 모듈 (강화 버전)
 - 레버리지 자동 설정
 - 실제 잔고 기반 수량 계산
 - 포지션 등록 보장
 - TP/SL 성공 여부와 관계없이 감시 등록
 - 청산 시 텔레그램 알림 + 로그 기록
 - 청산 실패시 경고 메시지 출력
"""

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
import telegram_bot

POSITIONS_TO_MONITOR: List[Dict[str, Any]] = []

def get_current_price(symbol: str) -> float:
    ticker = client.futures_symbol_ticker(symbol=symbol)
    return float(ticker["price"])

def place_entry_order(symbol: str, side: str, strategy_name: str) -> Dict[str, Any]:
    try:
        entry_price = get_current_price(symbol)

        try:
            client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        except Exception as e:
            logging.warning(f"[레버리지 설정 실패] {symbol}: {e}")

        try:
            balances = client.futures_account_balance()
            usdt_balance = next((b for b in balances if b["asset"] == "USDT"), None)
            if usdt_balance is None:
                raise Exception("USDT 잔고 정보를 찾을 수 없습니다.")
            usdt = float(usdt_balance["balance"])
        except Exception as e:
            logging.error(f"[잔고 조회 실패] {e}")
            return {}

        qty = utils.calculate_order_quantity(symbol, entry_price, balance=usdt)
        if qty <= 0:
            logging.error(f"[오류] 계산된 수량이 0 이하입니다: {qty}")
            return {}

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

        logging.info(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 (수량: {qty}, 체결가: {filled_price})")
        telegram_bot.send_message(f"[{strategy_name}] {symbol} {side} 진입! 수량: {qty}, 진입가: {filled_price}")

        tp_sl_success = True
        if not USE_MARKET_TP_SL:
            tp_sl_success = place_tp_sl_orders(symbol, side, filled_price, qty)
            if not tp_sl_success:
                logging.warning(f"[경고] TP/SL 지정가 주문 실패: {symbol}")

        # ✅ 무조건 감시 목록 등록 + 포지션 저장
        POSITIONS_TO_MONITOR.append(position)
        position_manager.add_position(position)

        return position

    except Exception as e:
        logging.error(f"[오류] 진입 주문 실패: {e}")
        return {}

def place_tp_sl_orders(symbol: str, side: str, entry_price: float, qty: float) -> bool:
    try:
        tp_price = utils.apply_slippage(entry_price, side, TP_SL_SLIPPAGE_RATE)
        sl_price = utils.apply_slippage(entry_price, side, -TP_SL_SLIPPAGE_RATE)
        side_tp = "SELL" if side.upper() == "LONG" else "BUY"

        client.futures_create_order(
            symbol=symbol,
            side=side_tp,
            type="TAKE_PROFIT_MARKET",
            stopPrice=round(tp_price, 2),
            closePosition=True,
            timeInForce="GTC"
        )

        client.futures_create_order(
            symbol=symbol,
            side=side_tp,
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
    closed = []

    for pos in POSITIONS_TO_MONITOR:
        try:
            current = get_current_price(pos["symbol"])
            tp = utils.apply_slippage(pos["entry_price"], pos["side"], TP_SL_SLIPPAGE_RATE)
            sl = utils.apply_slippage(pos["entry_price"], pos["side"], -TP_SL_SLIPPAGE_RATE)

            hit_tp = pos["side"] == "LONG" and current >= tp or pos["side"] == "SHORT" and current <= tp
            hit_sl = pos["side"] == "LONG" and current <= sl or pos["side"] == "SHORT" and current >= sl

            if hit_tp or hit_sl:
                pos["pnl"] = (tp - pos["entry_price"]) * pos["qty"] if hit_tp else (sl - pos["entry_price"]) * pos["qty"]
                logging.info(f"[청산] {pos['symbol']} {'TP' if hit_tp else 'SL'} 도달")
                telegram_bot.send_message(f"[{pos['strategy']}] {pos['symbol']} {pos['side']} 청산 완료! 손익: {pos['pnl']:.2f} USDT")
                closed.append(pos)

        except Exception as e:
            logging.error(f"[감시 오류] {pos['symbol']} 감시 실패: {e}")
            telegram_bot.send_message(f"[감시 오류] {pos['symbol']} 포지션 확인 중 문제 발생: {e}")

    for pos in closed:
        POSITIONS_TO_MONITOR.remove(pos)
        position_manager.remove_position(pos)
        trade_summary.add_trade_entry(pos)

def force_market_exit(position: Dict[str, Any]) -> None:
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
        telegram_bot.send_message(f"[강제 청산 실패] {position['symbol']}: {e}")

    if position in POSITIONS_TO_MONITOR:
        POSITIONS_TO_MONITOR.remove(position)
    position_manager.remove_position(position)
    trade_summary.add_trade_entry(position)
    telegram_bot.send_message(f"[{position['strategy']}] {position['symbol']} 강제 청산 완료")
