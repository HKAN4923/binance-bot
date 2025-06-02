# main.py
import sys
import time
import threading
import logging
import numpy as np
from decimal import Decimal, ROUND_DOWN
from config import (
    MAX_POSITIONS, ANALYSIS_INTERVAL_SEC, LEVERAGE,
    PRIMARY_THRESHOLD, AUX_COUNT_THRESHOLD,
    EMA_SHORT_LEN, EMA_LONG_LEN, VOLUME_SPIKE_MULTIPLIER,
    TP_RATIO, SL_RATIO, PIL_LOSS_THRESHOLD, PIL_PROFIT_THRESHOLD,
    LIMIT_ORDER_WAIT_BASE, LIMIT_OFFSET, PARTIAL_EXIT_RATIO,
    MAX_TRADE_DURATION
)
from utils import (
    to_kst, calculate_qty, get_top_100_volume_symbols,
    get_tradable_futures_symbols, get_tick_size
)
from telegram_notifier import send_telegram
from trade_summary import start_summary_scheduler
from position_monitor import PositionMonitor
from strategy import check_entry_multi, count_entry_signals, calculate_atr
from binance_client import (
    get_ohlcv, get_balance, get_mark_price,
    get_precision, create_market_order, create_stop_order,
    create_take_profit, create_limit_order, cancel_all_orders_for_symbol,
    get_open_position_amt
)

# 전역 변수
wins = 0
losses = 0
total_pnl = Decimal("0")  # 누적 실현 손익 (USDT)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# 메모리 상 포지션 기록
positions = {}
positions_lock = threading.Lock()

# 거래 로그
trade_log = []
trade_log_lock = threading.Lock()

def count_open_positions():
    cnt = 0
    with positions_lock:
        keys = list(positions.keys())
    for sym in keys:
        try:
            amt = get_open_position_amt(sym)
            if amt > 0:
                cnt += 1
            else:
                with positions_lock:
                    if sym in positions:
                        positions.pop(sym)
        except Exception as e:
            logging.error(f"{sym} get_open_position_amt 오류: {e}")
    return cnt

def compute_obv_signal(df):
    try:
        df = df.copy()
        df['change'] = df['close'].diff()
        df['vol_adj'] = df['volume'].where(df['change'] > 0, -df['volume'])
        df['obv'] = df['vol_adj'].cumsum()
        return 'long' if df['obv'].iloc[-1] > df['obv'].iloc[-2] else 'short'
    except:
        return None

def compute_volume_spike_signal(df):
    try:
        if len(df) < 21:
            return None
        prev_vols = df['volume'].iloc[-21:-1]
        mean_prev_vol = prev_vols.mean()
        last_vol = df['volume'].iloc[-1]
        last_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        if mean_prev_vol and last_vol > mean_prev_vol * VOLUME_SPIKE_MULTIPLIER:
            if last_close > prev_close:
                return 'long'
            elif last_close < prev_close:
                return 'short'
        return None
    except:
        return None

def compute_bollinger_signal(df):
    try:
        if len(df) < 20:
            return None
        df = df.copy()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['upper'] = df['sma20'] + 2 * df['std20']
        df['lower'] = df['sma20'] - 2 * df['std20']
        last_close = df['close'].iloc[-1]
        if last_close > df['upper'].iloc[-1]:
            return 'long'
        elif last_close < df['lower'].iloc[-1]:
            return 'short'
        return None
    except:
        return None

def cleanup_orphan_orders():
    while True:
        try:
            from binance_client import client
            open_orders = client.futures_get_open_orders()
            symbols_with_orders = set(o['symbol'] for o in open_orders)
            with positions_lock:
                tracked = set(positions.keys())
            for sym in symbols_with_orders:
                if sym not in tracked:
                    cancel_all_orders_for_symbol(sym)
            time.sleep(10)
        except Exception as e:
            logging.error(f"cleanup_orphan_orders 오류: {e}")
            time.sleep(10)

def monitor_position(sym):
    global wins, losses, total_pnl
    try:
        with positions_lock:
            pos_info = positions.get(sym)
        if not pos_info:
            return
        side = pos_info['side']
        entry_price = pos_info['entry_price']
        initial_quantity = pos_info['quantity']
        initial_count = pos_info['initial_match_count']
        primary_sig = pos_info['primary_sig']
        start_time = pos_info['start_time']
        _, qty_precision, min_qty = get_precision(sym)
        quant = Decimal(f"1e-{qty_precision}")

        realized_usdt = Decimal("0")
        remaining_qty = initial_quantity
        partial_exit_done = False  # 부분 청산 완료 여부 플래그 (1회만 실행)

        while True:
            time.sleep(10)
            amt = get_open_position_amt(sym)
            _, _, min_qty_val = get_precision(sym)
            if amt < min_qty_val:
                amt = 0

            # 1) 전량 청산 상태 처리 (amt == 0)
            if amt == 0:
                # 진입 이후 이미 잔량이 다 소진된 상태: 전체 실현 손익 계산
                mark_price = Decimal(str(get_mark_price(sym)))
                if remaining_qty > 0:
                    if primary_sig == 'long':
                        pnl_usdt_final = (mark_price - entry_price) * remaining_qty
                    else:
                        pnl_usdt_final = (entry_price - mark_price) * remaining_qty
                    realized_usdt += pnl_usdt_final
                    remaining_qty = Decimal("0")
                total_pnl += realized_usdt

                # 승패 판단
                if realized_usdt > 0:
                    wins += 1
                    result = "WIN"
                else:
                    losses += 1
                    result = "LOSS"
                total_trades = wins + losses
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

                # trade_log 기록
                with trade_log_lock:
                    trade_log.append({
                        'timestamp': time.time(),
                        'symbol': sym,
                        'side': primary_sig,
                        'pnl_pct': float((realized_usdt / (entry_price * initial_quantity)) * 100),
                        'pnl_usdt': float(realized_usdt),
                        'exit_type': 'full_close'
                    })

                # EXIT 알림
                msg = (
                    f"<b>🔸 EXIT: {sym}</b>\n"
                    f"▶ 방향: {primary_sig.upper()}\n"
                    f"▶ 청산 이유: FULL CLOSE\n"
                    f"▶ 실현 손익: {realized_usdt:.2f} USDT\n"
                    f"▶ 결과: {result}\n"
                    f"▶ 누적 기록: {wins}승 {losses}패 (승률 {win_rate:.2f}%)"
                )
                send_telegram(msg)

                with positions_lock:
                    if sym in positions:
                        positions.pop(sym)
                break

            # 2) PnL 계산
            mark_price = Decimal(str(get_mark_price(sym)))
            if primary_sig == 'long':
                pnl = (mark_price - entry_price) / entry_price
            else:
                pnl = (entry_price - mark_price) / entry_price

            # 3) 30분 경과 후 신호 없으면 즉시 청산
            elapsed = time.time() - start_time
            if elapsed >= 30 * 60 and elapsed < MAX_TRADE_DURATION:
                df1_tmp = get_ohlcv(sym, '1m', limit=50)
                df5_tmp = get_ohlcv(sym, '5m', limit=50)
                if (df1_tmp is not None and len(df1_tmp) >= 50
                        and df5_tmp is not None and len(df5_tmp) >= 50):
                    sig1_l2, sig1_s2 = count_entry_signals(df1_tmp)
                    sig5_l2, sig5_s2 = count_entry_signals(df5_tmp)
                    total_signals = sig1_l2 + sig1_s2 + sig5_l2 + sig5_s2
                    if total_signals == 0:
                        remaining_amt2 = get_open_position_amt(sym)
                        if remaining_amt2 > 0:
                            create_market_order(
                                sym,
                                "SELL" if side == "long" else "BUY",
                                float(remaining_amt2),
                                reduceOnly=True
                            )
                            mark_price2 = Decimal(str(get_mark_price(sym)))
                            if primary_sig == 'long':
                                pnl_usdt2 = (mark_price2 - entry_price) * remaining_amt2
                            else:
                                pnl_usdt2 = (entry_price - mark_price2) * remaining_amt2
                            realized_usdt += pnl_usdt2
                            total_pnl += realized_usdt

                            if realized_usdt > 0:
                                wins += 1
                                result2 = "WIN"
                            else:
                                losses += 1
                                result2 = "LOSS"
                            total_trades2 = wins + losses
                            win_rate2 = (wins / total_trades2 * 100) if total_trades2 > 0 else 0

                            with trade_log_lock:
                                trade_log.append({
                                    'timestamp': time.time(),
                                    'symbol': sym,
                                    'side': primary_sig,
                                    'pnl_pct': float((realized_usdt / (entry_price * initial_quantity)) * 100),
                                    'pnl_usdt': float(realized_usdt),
                                    'exit_type': 'no_signal'
                                })

                            send_telegram(
                                f"<b>🔸 EXIT: {sym}</b>\n"
                                f"▶ 방향: {primary_sig.upper()}\n"
                                f"▶ 청산 이유: NO SIGNAL AFTER 30m\n"
                                f"▶ 실현 손익: {realized_usdt:.2f} USDT\n"
                                f"▶ 결과: {result2}\n"
                                f"▶ 누적 기록: {wins}승 {losses}패 (승률 {win_rate2:.2f}%)"
                            )
                            with positions_lock:
                                if sym in positions:
                                    positions.pop(sym)
                        break

            # 4) 자동 익절/손절 (잔량 전량 청산)
            remaining_amt = amt
            if remaining_amt > 0:
                if pnl >= PIL_PROFIT_THRESHOLD:  # 익절
                    if primary_sig == 'long':
                        pnl_usdt_partial = (mark_price - entry_price) * remaining_amt
                    else:
                        pnl_usdt_partial = (entry_price - mark_price) * remaining_amt
                    realized_usdt += pnl_usdt_partial
                    create_market_order(
                        sym,
                        "SELL" if side == "long" else "BUY",
                        float(remaining_amt),
                        reduceOnly=True
                    )
                    total_pnl += realized_usdt
                    if realized_usdt > 0:
                        wins += 1
                        result = "WIN"
                    else:
                        losses += 1
                        result = "LOSS"
                    total_trades = wins + losses
                    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

                    with trade_log_lock:
                        trade_log.append({
                            'timestamp': time.time(),
                            'symbol': sym,
                            'side': primary_sig,
                            'pnl_pct': float((realized_usdt / (entry_price * initial_quantity)) * 100),
                            'pnl_usdt': float(realized_usdt),
                            'exit_type': 'auto_tp'
                        })

                    send_telegram(
                        f"<b>✅ AUTO-TP: {sym}</b>\n"
                        f"▶ 방향: {primary_sig.upper()}\n"
                        f"▶ 실현 손익: {realized_usdt:.2f} USDT\n"
                        f"▶ 결과: {result}\n"
                        f"▶ 누적 기록: {wins}승 {losses}패 (승률 {win_rate:.2f}%)"
                    )
                    with positions_lock:
                        if sym in positions:
                            positions.pop(sym)
                    break
                elif pnl <= PIL_LOSS_THRESHOLD:  # 손절
                    if primary_sig == 'long':
                        pnl_usdt_partial = (mark_price - entry_price) * remaining_amt
                    else:
                        pnl_usdt_partial = (entry_price - mark_price) * remaining_amt
                    realized_usdt += pnl_usdt_partial
                    create_market_order(
                        sym,
                        "SELL" if side == "long" else "BUY",
                        float(remaining_amt),
                        reduceOnly=True
                    )
                    total_pnl += realized_usdt
                    if realized_usdt > 0:
                        wins += 1
                        result = "WIN"
                    else:
                        losses += 1
                        result = "LOSS"
                    total_trades = wins + losses
                    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

                    with trade_log_lock:
                        trade_log.append({
                            'timestamp': time.time(),
                            'symbol': sym,
                            'side': primary_sig,
                            'pnl_pct': float((realized_usdt / (entry_price * initial_quantity)) * 100),
                            'pnl_usdt': float(realized_usdt),
                            'exit_type': 'auto_sl'
                        })

                    send_telegram(
                        f"<b>❌ AUTO-SL: {sym}</b>\n"
                        f"▶ 방향: {primary_sig.upper()}\n"
                        f"▶ 실현 손익: {realized_usdt:.2f} USDT\n"
                        f"▶ 결과: {result}\n"
                        f"▶ 누적 기록: {wins}승 {losses}패 (승률 {win_rate:.2f}%)"
                    )
                    with positions_lock:
                        if sym in positions:
                            positions.pop(sym)
                    break

            # 5) 부분 익절: 신호 하나 줄고 PnL > 0일 때만 (1회만 실행)
            if not partial_exit_done:
                df1 = get_ohlcv(sym, '1m', limit=50)
                df5 = get_ohlcv(sym, '5m', limit=50)
                if df1 is not None and len(df1) >= 50 and df5 is not None and len(df5) >= 50:
                    sig1_l, sig1_s = count_entry_signals(df1)
                    sig5_l, sig5_s = count_entry_signals(df5)
                    current_count = max(sig1_l, sig1_s) + max(sig5_l, sig5_s)

                    # 신호 1개 감소 시 50% 부분 청산
                    if current_count == initial_count - 1 and pnl > 0:
                        take_amt = (Decimal(str(remaining_amt)) * PARTIAL_EXIT_RATIO).quantize(quant, rounding=ROUND_DOWN)
                        if take_amt > min_qty_val:
                            if primary_sig == 'long':
                                pnl_usdt_partial = (mark_price - entry_price) * take_amt
                            else:
                                pnl_usdt_partial = (entry_price - mark_price) * take_amt
                            realized_usdt += pnl_usdt_partial
                            remaining_qty -= take_amt
                            create_market_order(
                                sym,
                                "SELL" if side == "long" else "BUY",
                                float(take_amt),
                                reduceOnly=True
                            )
                            
                            # 부분 청산 알림
                            msg = (
                                f"<b>🔸 PARTIAL EXIT: {sym}</b>\n"
                                f"▶ 방향: {primary_sig.upper()}\n"
                                f"▶ 부분 청산량: {take_amt:.4f}\n"
                                f"▶ 부분 실현 손익: {pnl_usdt_partial:.2f} USDT"
                            )
                            send_telegram(msg)
                            
                            # 트레이드 로그 기록
                            with trade_log_lock:
                                trade_log.append({
                                    'timestamp': time.time(),
                                    'symbol': sym,
                                    'side': primary_sig,
                                    'pnl_pct': float((pnl_usdt_partial / (entry_price * take_amt)) * 100),
                                    'pnl_usdt': float(pnl_usdt_partial),
                                    'exit_type': 'partial'
                                })
                            
                            partial_exit_done = True  # 1회만 실행

            # 6) 잔량이 최소수량 미만일 때 최종 청산 + EXIT
            remaining_amt = get_open_position_amt(sym)
            if 0 < remaining_amt < min_qty_val:
                create_market_order(
                    sym,
                    "SELL" if side == "long" else "BUY",
                    float(remaining_amt),
                    reduceOnly=True
                )
                mark_price2 = Decimal(str(get_mark_price(sym)))
                if primary_sig == 'long':
                    final_pnl_usdt = (mark_price2 - entry_price) * remaining_amt
                else:
                    final_pnl_usdt = (entry_price - mark_price2) * remaining_amt
                realized_usdt += final_pnl_usdt
                remaining_qty = Decimal("0")
                total_pnl += realized_usdt
                if realized_usdt > 0:
                    wins += 1
                    result = "WIN"
                else:
                    losses += 1
                    result = "LOSS"
                total_trades = wins + losses
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

                with trade_log_lock:
                    trade_log.append({
                        'timestamp': time.time(),
                        'symbol': sym,
                        'side': primary_sig,
                        'pnl_pct': float((realized_usdt / (entry_price * initial_quantity)) * 100),
                        'pnl_usdt': float(realized_usdt),
                        'exit_type': 'final_close'
                    })

                send_telegram(
                    f"<b>🔚 FINAL CLOSE: {sym}</b>\n"
                    f"▶ 방향: {primary_sig.upper()}\n"
                    f"▶ 청산 이유: MIN QTY CLOSE\n"
                    f"▶ 실현 손익: {realized_usdt:.2f} USDT\n"
                    f"▶ 결과: {result}\n"
                    f"▶ 누적 기록: {wins}승 {losses}패 (승률 {win_rate:.2f}%)"
                )
                with positions_lock:
                    if sym in positions:
                        positions.pop(sym)
                break

            time.sleep(0.1)

    except Exception as e:
        logging.error(f"{sym} 모니터링 오류: {e}")
        # 오류 발생 시 강제 청산
        try:
            amt = get_open_position_amt(sym)
            if amt > 0:
                create_market_order(
                    sym,
                    "SELL" if primary_sig == "long" else "BUY",
                    float(amt),
                    reduceOnly=True
                )
                # 오류 로깅
                with trade_log_lock:
                    trade_log.append({
                        'timestamp': time.time(),
                        'symbol': sym,
                        'side': primary_sig,
                        'pnl_pct': 0,
                        'pnl_usdt': 0,
                        'exit_type': 'error'
                    })
                # 알림
                send_telegram(f"<b>⛔ ERROR EXIT: {sym}</b>\n▶ 오류로 인한 강제 청산")
        finally:
            with positions_lock:
                if sym in positions:
                    positions.pop(sym)

def analyze_market():
    tradable_symbols = []
    last_update = 0
    while True:
        try:
            now_ts = time.time()
            if now_ts - last_update > 1800 or not tradable_symbols:
                tradable_symbols = get_top_100_volume_symbols()
                last_update = now_ts
                if not tradable_symbols:
                    tradable_symbols = get_tradable_futures_symbols()

            current_positions = count_open_positions()
            now = to_kst(time.time())
            logging.info(f"{now.strftime('%H:%M:%S')} 분석 중 ({current_positions}/{MAX_POSITIONS})")
            if current_positions >= MAX_POSITIONS:
                time.sleep(ANALYSIS_INTERVAL_SEC)
                continue

            for sym in tradable_symbols:
                if count_open_positions() >= MAX_POSITIONS:
                    break
                with positions_lock:
                    if sym in positions:
                        continue

                df1 = get_ohlcv(sym, '1m', limit=50)
                df5 = get_ohlcv(sym, '5m', limit=50)
                if df1 is None or len(df1) < 50 or df5 is None or len(df5) < 50:
                    continue

                sig1 = check_entry_multi(df1, threshold=PRIMARY_THRESHOLD)
                sig5 = check_entry_multi(df5, threshold=PRIMARY_THRESHOLD)

                primary_sig = None
                primary_tf = None
                if sig1 and not sig5:
                    primary_sig, primary_tf = sig1, '1m'
                elif sig5 and not sig1:
                    primary_sig, primary_tf = sig5, '5m'
                elif sig1 == sig5:
                    primary_sig, primary_tf = sig1, 'both'
                else:
                    continue

                aux = []
                df30 = get_ohlcv(sym, '30m', limit=EMA_LONG_LEN + 2)
                if df30 is not None and len(df30) >= EMA_LONG_LEN:
                    df30['ema_s'] = df30['close'].ewm(span=EMA_SHORT_LEN).mean()
                    df30['ema_l'] = df30['close'].ewm(span=EMA_LONG_LEN).mean()
                    if df30['ema_s'].iloc[-1] > df30['ema_l'].iloc[-1]:
                        aux.append('long')
                    else:
                        aux.append('short')
                obv = compute_obv_signal(df1)
                if obv:
                    aux.append(obv)
                vol = compute_volume_spike_signal(df1)
                if vol:
                    aux.append(vol)
                bb = compute_bollinger_signal(df1)
                if bb:
                    aux.append(bb)

                match_count = aux.count(primary_sig)
                if match_count < AUX_COUNT_THRESHOLD:
                    continue

                balance = get_balance()
                mark_price = get_mark_price(sym)
                price_prec, qty_prec, min_qty = get_precision(sym)
                sig1_l, sig1_s = count_entry_signals(df1)
                sig5_l, sig5_s = count_entry_signals(df5)
                initial_count = max(sig1_l, sig1_s) + max(sig5_l, sig5_s)
                side = 'BUY' if primary_sig == 'long' else 'SELL'
                qty = calculate_qty(balance, Decimal(str(mark_price)), LEVERAGE, Decimal("0.3"), qty_prec, min_qty)
                if qty == 0:
                    continue

                atr_series = calculate_atr(df1, length=14)
                atr = atr_series.iloc[-1] if (atr_series is not None and not np.isnan(atr_series.iloc[-1])) else None
                if atr:
                    dynamic_wait = max(2, min(10, int(atr * 100)))
                else:
                    dynamic_wait = LIMIT_ORDER_WAIT_BASE

                quant_price = Decimal(f"1e-{price_prec}")
                tick_size = get_tick_size(sym)
                if side == 'BUY':
                    limit_price = (Decimal(str(mark_price)) * (Decimal("1") - LIMIT_OFFSET)).quantize(quant_price, rounding=ROUND_DOWN)
                else:
                    limit_price = (Decimal(str(mark_price)) * (Decimal("1") + LIMIT_OFFSET)).quantize(quant_price, rounding=ROUND_DOWN)

                entry_order = create_limit_order(sym, side, float(qty), float(limit_price))
                if not entry_order:
                    continue
                order_id = entry_order.get('orderId')
                time.sleep(dynamic_wait)

                try:
                    from binance_client import client
                    order_info = client.futures_get_order(symbol=sym, orderId=order_id)
                except Exception as e:
                    logging.error(f"주문 확인 실패: {e}")
                    cancel_all_orders_for_symbol(sym)
                    continue

                if order_info.get('status') != 'FILLED':
                    cancel_all_orders_for_symbol(sym)
                    continue

                fills = order_info.get('fills')
                entry_price = Decimal(str(fills[0]['price'])) if fills else Decimal(str(mark_price))

                if primary_sig == 'long':
                    tp = (entry_price * (Decimal("1") + TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    base_sl = (entry_price * (Decimal("1") - SL_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    sl = max(base_sl, entry_price - tick_size * 2)
                    tp_ord = create_take_profit(sym, 'SELL', float(tp), float(qty))
                    sl_ord = create_stop_order(sym, 'SELL', float(sl), float(qty))
                    if not sl_ord:
                        logging.warning(f"{sym} - 기본 SL 주문 실패, TP_RATIO 기반 SL 재설정 중...")
                        alt_sl = (entry_price * (Decimal("1") - TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                        sl_ord = create_stop_order(sym, 'SELL', float(alt_sl), float(qty))
                        if not sl_ord:
                            logging.warning(f"{sym} - TP_RATIO 기반 SL 주문도 실패, 1% SL 고정으로 재설정 중...")
                            fixed_sl = (entry_price * (Decimal("0.99"))).quantize(quant_price, rounding=ROUND_DOWN)
                            sl_ord = create_stop_order(sym, 'SELL', float(fixed_sl), float(qty))
                            if not sl_ord:
                                send_telegram(f"⚠️ {sym} SL 주문이 연속 실패했습니다. SL이 걸리지 않았습니다.")
                else:
                    tp = (entry_price * (Decimal("1") - TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    base_sl = (entry_price * (Decimal("1") + SL_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    sl = min(base_sl, entry_price + tick_size * 2)
                    tp_ord = create_take_profit(sym, 'BUY', float(tp), float(qty))
                    sl_ord = create_stop_order(sym, 'BUY', float(sl), float(qty))
                    if not sl_ord:
                        logging.warning(f"{sym} - 기본 SL 주문 실패, TP_RATIO 기반 SL 재설정 중...")
                        alt_sl = (entry_price * (Decimal("1") + TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                        sl_ord = create_stop_order(sym, 'BUY', float(alt_sl), float(qty))
                        if not sl_ord:
                            logging.warning(f"{sym} - TP_RATIO 기반 SL 주문도 실패, 1% SL 고정으로 재설정 중...")
                            fixed_sl = (entry_price * (Decimal("1.01"))).quantize(quant_price, rounding=ROUND_DOWN)
                            sl_ord = create_stop_order(sym, 'BUY', float(fixed_sl), float(qty))
                            if not sl_ord:
                                send_telegram(f"⚠️ {sym} SL 주문이 연속 실패했습니다. SL이 걸리지 않았습니다.")

                tp_id = tp_ord.get('orderId') if tp_ord else None
                sl_id = sl_ord.get('orderId') if sl_ord else None

                with positions_lock:
                    positions[sym] = {
                        'side': primary_sig,
                        'quantity': Decimal(str(qty)),
                        'entry_price': entry_price,
                        'initial_match_count': initial_count,
                        'primary_sig': primary_sig,
                        'start_time': time.time(),
                        'tp_order_id': tp_id,
                        'sl_order_id': sl_id
                    }
                msg = (
                    f"<b>🔹 ENTRY: {sym}</b>\n"
                    f"▶ 방향: {primary_sig.upper()}\n"
                    f"▶ 초기 신호: {initial_count}\n"
                    f"▶ 진입가: {entry_price:.4f}\n"
                    f"▶ TP: {tp}\n"
                    f"▶ SL: {sl}"
                )
                send_telegram(msg)

                threading.Thread(target=monitor_position, args=(sym,), daemon=True).start()
                time.sleep(0.05)

            time.sleep(ANALYSIS_INTERVAL_SEC)
        except Exception as e:
            logging.error(f"Error in analyze_market: {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        send_telegram("<b>🤖 봇 시작</b>")
    except Exception as e:
        logging.error(f"텔레그램 시작 알림 실패: {e}")
    
    start_summary_scheduler(trade_log, trade_log_lock)
    pos_mon = PositionMonitor(positions, positions_lock)
    pos_mon.start()
    threading.Thread(target=cleanup_orphan_orders, daemon=True).start()
    threading.Thread(target=analyze_market, daemon=True).start()

    try:
        while True:
            logging.info("봇 정상 대기 중...")
            time.sleep(30)
    except KeyboardInterrupt:
        pos_mon.stop()
        send_telegram("<b>🛑 봇 수동 종료</b>")
        sys.exit(0)