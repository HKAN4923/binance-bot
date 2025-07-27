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
from trade_summary import summarize_by_strategy


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
            pnl_rate = 0.0
            pnl_usdt = 0.0
            lines.append("❗ 체결가 0으로 손익률 계산 불가")
        else:
            side_factor = 1 if side == "BUY" else -1
            pnl_rate = ((current_price - entry_price) / entry_price) * 100 * side_factor
            pnl_usdt = (current_price - entry_price) * side_factor
            lines.append(f"💰 손익률: {pnl_rate:+.2f}%")
            lines.append(f"📊 손익: {pnl_usdt:+.2f} USDT")

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
        lines.append(f"📈 전체 손익: {total_pnl:+.2f} USDT")
        lines.append(f"🎯 전체 승률: {total_win_rate:.1f}%")

        send_message("\n".join(lines))

    except Exception as e:
        logging.error(f"[텔레그램] 청산 메시지 전송 실패: {e}")


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
        if side not in ["BUY", "SELL"]:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 잘못된 side 값: {side}")
            return

        ticker = client.futures_symbol_ticker(symbol=symbol)
        raw_price = ticker.get("price")
        if raw_price is None:
            logging.warning(f"[스킵] {symbol} 진입 실패 - 현재가 조회 실패")
            return

        entry_price = round_price(symbol, float(raw_price))
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

        fill_price = order.get("avgFillPrice") or order.get("avgPrice") or raw_price
        fill_price = float(fill_price) if fill_price else float(raw_price)
        if fill_price == 0:
            logging.warning(f"[진입 오류] {symbol} 체결가가 0입니다. 진입 무시")
            return

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


# ✅ monitor_positions 함수는 기존에 제공한 것 그대로 사용하시면 됩니다.
# 이미 감시 구조, TP/SL, 타임컷, 신호 무효화 모두 정상 처리되도록 설계되어 있습니다.
