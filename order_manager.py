# ✅ WebSocket 실시간 가격 기반 진입 + 포지션 감시 포함 order_manager.py 전체 통합본

import logging
from datetime import datetime, timedelta
from binance.exceptions import BinanceAPIException

from binance_client import client
from risk_config import LEVERAGE, TP_SL_SETTINGS, TIME_CUT_BY_STRATEGY
from utils import calculate_order_quantity, round_price, round_quantity, get_futures_balance, cancel_all_orders, to_kst
from telegram_bot import send_message
from position_manager import add_position, remove_position, get_positions
from trade_summary import summarize_by_strategy
from price_ws import get_price as ws_price

def send_exit_summary(symbol, strategy, reason, entry_price, current_price, entry_time, side):
    try:
        now = datetime.utcnow()
        elapsed_min = int((now - entry_time).total_seconds() / 60)
        lines = [
            f"✅ [청산] {strategy} 전략 - {symbol}",
            f"🎯 사유: {reason}",
            f"⏱ 경과: {elapsed_min}분",
        ]

        if entry_price == 0:
            logging.warning(f"[청산경고] {symbol} entry_price가 0입니다. 손익률 계산 생략")
            lines.append("❗ 체결가 0으로 손익률 계산 불가")
        else:
            side_factor = 1 if side == "BUY" else -1
            pnl_rate = ((current_price - entry_price) / entry_price) * 100 * side_factor
            pnl_usdt = (current_price - entry_price) * side_factor
            lines.append(f"💰 손익률: {pnl_rate:+.2f}%")
            lines.append(f"📈 손익: {pnl_usdt:+.2f} USDT")

        lines.append("")
        summary = summarize_by_strategy()
        lines.append("📊 전략별 누적 요약")
        total_pnl = 0
        total_trades = 0
        total_wins = 0

        for strat, data in summary.items():
            lines.append(
                f"[{strat}] 진입: {data['trades']}회 | 승률: {data['win_rate']:.1f}% | 손익: {data['pnl']:+.2f} USDT"
            )
            total_pnl += data["pnl"]
            total_trades += data["trades"]
            total_wins += data["wins"]

        total_win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0.0
        lines.append("")
        lines.append(f"📊 전체 손익: {total_pnl:+.2f} USDT")
        lines.append(f"🎯 전체 승률: {total_win_rate:.1f}%")

        send_message("\n".join(lines))

    except Exception as e:
        logging.error(f"[텔레그램] 청산 메시지 전송 실패: {e}")

def place_entry_order(symbol: str, side: str, strategy_name: str) -> None:
    try:
        side = side.upper()
        if side not in ["BUY", "SELL"]:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 잘못된 side 값")
            return

        entry_price = ws_price(symbol)
        if entry_price is None:
            logging.warning(f"[스킵] {symbol} 진입 실패 - WebSocket 가격 없음")
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

        fills = order.get("fills")
        if fills and isinstance(fills, list):
            fill_price = float(fills[0].get("price", entry_price))
        else:
            fill_price = float(order.get("avgFillPrice") or order.get("avgPrice") or entry_price)

        if fill_price == 0:
            logging.warning(f"[진입 오류] {symbol} 체결가가 0입니다. 진입 무시")
            return

        logging.info(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 (수량: {quantity}, 체결가: {fill_price})")
        send_message(f"[진입] {strategy_name} 전략으로 {symbol} {side} 진입 완료 (수량: {quantity}, 체결가: {fill_price})")

        from order_manager import place_tp_sl_orders
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
        now = datetime.utcnow()
        positions = get_positions()
        for pos in positions:
            symbol = pos["symbol"]
            entry_price = float(pos["entry_price"])
            entry_time = datetime.fromisoformat(pos["entry_time"])
            side = pos["side"]
            strategy = pos["strategy"]
            current_price = ws_price(symbol)

            if current_price is None:
                continue

            tp_pct = TP_SL_SETTINGS[strategy]["tp"]
            sl_pct = TP_SL_SETTINGS[strategy]["sl"]
            direction = 1 if side == "BUY" else -1
            tp_price = entry_price * (1 + direction * tp_pct)
            sl_price = entry_price * (1 - direction * sl_pct)

            # TP or SL 도달
            if (side == "BUY" and current_price >= tp_price) or (side == "SELL" and current_price <= tp_price):
                logging.info(f"[TP] {symbol} {strategy} TP 도달 → 시장가 청산")
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY", type="MARKET", quantity=round_quantity(symbol, calculate_order_quantity(symbol, entry_price, get_futures_balance())))
                send_exit_summary(symbol, strategy, "TP 도달", entry_price, current_price, entry_time, side)
                remove_position(symbol)
                continue

            if (side == "BUY" and current_price <= sl_price) or (side == "SELL" and current_price >= sl_price):
                logging.info(f"[SL] {symbol} {strategy} SL 도달 → 시장가 청산")
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY", type="MARKET", quantity=round_quantity(symbol, calculate_order_quantity(symbol, entry_price, get_futures_balance())))
                send_exit_summary(symbol, strategy, "SL 도달", entry_price, current_price, entry_time, side)
                remove_position(symbol)
                continue

            # 타임컷
            minutes_elapsed = (now - entry_time).total_seconds() / 60
            cutoff = TIME_CUT_BY_STRATEGY.get(strategy)
            if cutoff and minutes_elapsed > cutoff:
                logging.info(f"[타임컷] {symbol} {strategy} 경과시간 초과 → 시장가 청산")
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY", type="MARKET", quantity=round_quantity(symbol, calculate_order_quantity(symbol, entry_price, get_futures_balance())))
                send_exit_summary(symbol, strategy, "타임컷", entry_price, current_price, entry_time, side)
                remove_position(symbol)

    except Exception as e:
        logging.error(f"[감시 오류] monitor_positions 실패: {e}")
