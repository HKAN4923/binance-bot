import logging
from datetime import datetime
from binance.exceptions import BinanceAPIException

from binance_client import client
from risk_config import LEVERAGE, TP_SL_SETTINGS, TIME_CUT_BY_STRATEGY
from utils import calculate_order_quantity, round_price, round_quantity, get_futures_balance, cancel_all_orders
from telegram_bot import send_message
from trade_summary import summarize_by_strategy
from position_manager import (
    add_position,
    remove_position,
    get_positions,
    is_duplicate,
    is_in_cooldown,
    load_positions as get_positions_from_log
)

def send_exit_summary(symbol, strategy, reason, entry_price, current_price, entry_time, side):
    try:
        now = datetime.utcnow()
        elapsed_min = int((now - entry_time).total_seconds() / 60)
        side_factor = 1 if side == "BUY" else -1
        pnl_rate = ((current_price - entry_price) / entry_price) * 100 * side_factor
        pnl_usdt = (current_price - entry_price) * side_factor

        lines = [
            f"✅ [출사] {strategy} 전략 - {symbol}",
            f"🎯 사유: {reason}",
            f"⏱ 경간: {elapsed_min}분",
            f"💰 손익률: {pnl_rate:+.2f}%",
            f"📊 손익: {pnl_usdt:+.2f} USDT",
            ""
        ]

        summary = summarize_by_strategy()
        lines.append("\ud83d\udcca \uc804\ub7b5\ubcc4 \ub204\uc801 \uc694약")

        total_pnl = 0
        total_trades = 0
        total_wins = 0

        for strat, data in summary.items():
            lines.append(
                f"[{strat}] \uc9c4입: {data['trades']}\ud68c | \uc2b9\ub960: {data['win_rate']:.1f}% | \uc190익: {data['pnl']:+.2f} USDT"
            )
            total_pnl += data["pnl"]
            total_trades += data["trades"]
            total_wins += data["wins"]

        total_win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0.0

        lines.append("")
        lines.append(f"📈 \uc804체 \uc190익: {total_pnl:+.2f} USDT")
        lines.append(f"🎯 \uc804체 \uc2b9\ub960: {total_win_rate:.1f}%")

        send_message("\n".join(lines))

    except Exception as e:
        logging.error(f"[\ud1a0\ub9c8\uae45] \ucc38사 \uba54시지 \uc804송 \uc2e4패: {e}")

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
        logging.error(f"[\uc624\ub958] TP/SL \uc9c0정가 \uc8fc\ubb38 \uc2e4패: {e}")
        return False, False
    except Exception as e:
        logging.error(f"[\uc624\ub958] TP/SL \uc8fc\ubb38 \uc2e4패: {e}")
        return False, False


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

            # 감시 상태 출력
            elapsed_min = int((now - entry_time).total_seconds() / 60)
            logging.info(
                f"[감시중] {symbol} 전략: {strategy} | 진입가: {entry_price:.4f} | 현재가: {current_price:.4f} | 경과: {elapsed_min}분"
            )

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

            if is_tp_hit:
                logging.info(f"[TP] {symbol} {strategy} TP 도달 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_exit_summary(symbol, strategy, "TP 도달", entry_price, current_price, entry_time, side)
                continue

            if is_sl_hit:
                logging.info(f"[SL] {symbol} {strategy} SL 도달 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_exit_summary(symbol, strategy, "SL 도달", entry_price, current_price, entry_time, side)
                continue

            # 신호 반전 체크
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
                        send_exit_summary(symbol, strategy, "신호 무효화", entry_price, current_price, entry_time, side)
                        continue
                except Exception as e:
                    logging.error(f"[감시 오류] {symbol} {strategy} 신호판단 실패: {e}")

            max_minutes = TIME_CUT_BY_STRATEGY.get(strategy.upper(), 120)
            if (now - entry_time).total_seconds() > max_minutes * 60:
                logging.info(f"[타임컷] {symbol} 전략 {strategy} 시간 초과 → 시장가 청산")
                cancel_all_orders(symbol)
                client.futures_create_order(symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                                            type="MARKET", quantity=abs(amt), reduceOnly=True)
                remove_position(symbol, strategy)
                send_exit_summary(symbol, strategy, "시간 초과", entry_price, current_price, entry_time, side)

    except Exception as e:
        logging.error(f"[감시 오류] 포지션 감시 중 오류 발생: {e}")