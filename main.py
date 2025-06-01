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
    LIMIT_ORDER_WAIT_BASE, LIMIT_OFFSET
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
    client, get_ohlcv, get_balance, get_mark_price,
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
                    positions.pop(sym, None)
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
    global wins, losses
    try:
        with positions_lock:
            pos_info = positions.get(sym)
        if not pos_info:
            return
        side = pos_info['side']
        entry_price = pos_info['entry_price']
        quantity = pos_info['quantity']
        initial_count = pos_info['initial_match_count']
        primary_sig = pos_info['primary_sig']
        _, qty_precision, _ = get_precision(sym)
        quant = Decimal(f"1e-{qty_precision}")

        while True:
            time.sleep(10)
            amt = get_open_position_amt(sym)

            # 포지션이 완전히 사라졌다면(청산됨)
            if amt == 0:
                total_pnl += pnl_usdt
                mark_price = Decimal(str(get_mark_price(sym)))
                if primary_sig == 'long':
                    pnl_pct = (mark_price - entry_price) / entry_price
                    pnl_usdt = (mark_price - entry_price) * quantity
                else:
                    pnl_pct = (entry_price - mark_price) / entry_price
                    pnl_usdt = (entry_price - mark_price) * quantity

                # 누적 승/패 업데이트
                if pnl_pct > 0:
                    wins += 1
                else:
                    losses += 1

                # trade_log에 기록
                with trade_log_lock:
                    trade_log.append({
                        'timestamp': time.time(),
                        'symbol': sym,
                        'side': primary_sig,
                        'pnl_pct': float(pnl_pct),
                        'pnl_usdt': float(pnl_usdt)
                    })

                # Telegram 청산 알림
                msg = (
                    f"<b>🔸 EXIT: {sym}</b>\n"
                    f"▶ 방향: {primary_sig.upper()}\n"
                    f"▶ 실현 손익: {pnl_usdt:.2f} USDT ({pnl_pct * 100:.2f}%)\n"
                    f"▶ 누적 기록: {wins}승 {losses}패"/ 총손익: {total_pnl:.2f} USDT"
                )
                send_telegram(msg)

                # 메모리에서 제거
                with positions_lock:
                    positions.pop(sym, None)
                break

            # 포지션이 남아 있는 경우 PnL 계산
            mark_price = Decimal(str(get_mark_price(sym)))
            if primary_sig == 'long':
                pnl = (mark_price - entry_price) / entry_price
            else:
                pnl = (entry_price - mark_price) / entry_price

            # PnL 0.2% 도달 시 전량 매도
            if pnl >= Decimal("0.002"):
                remaining_amt = get_open_position_amt(sym)
                if remaining_amt > 0:
                    create_market_order(
                        sym,
                        "SELL" if side == "long" else "BUY",
                        float(remaining_amt),
                        reduceOnly=True
                    )
                    
            elif pnl <= Decimal("-0.005"):
                create_market_order(
                    sym,
                    "SELL" if side == "long" else "BUY",
                    float(remaining_amt),
                    reduceOnly=True
                    
                    with positions_lock:
                        positions.pop(sym, None)
                    break
                )

            # 1) 손절 조건
            if pnl < -PIL_LOSS_THRESHOLD:
                df1 = get_ohlcv(sym, '1m', limit=50)
                if df1 is not None and len(df1) >= 50:
                    from strategy import check_reversal_multi
                    if not check_reversal_multi(df1, threshold=2):
                        create_market_order(
                            sym,
                            "SELL" if side == "long" else "BUY",
                            float(quantity),
                            reduceOnly=True
                        )
                        with positions_lock:
                            positions.pop(sym, None)
                        break

            # 2) 익절 조건
            if pnl > PIL_PROFIT_THRESHOLD:
                df1 = get_ohlcv(sym, '1m', limit=50)
                if df1 is not None and len(df1) >= 50:
                    from strategy import check_reversal_multi
                    if check_reversal_multi(df1, threshold=2):
                        create_market_order(
                            sym,
                            "SELL" if side == "long" else "BUY",
                            float(quantity),
                            reduceOnly=True
                        )
                        with positions_lock:
                            positions.pop(sym, None)
                        break

            # 3) 부분 익절/잔량 청산
            df1 = get_ohlcv(sym, '1m', limit=50)
            df5 = get_ohlcv(sym, '5m', limit=50)
            if df1 is None or df5 is None:
                continue
            sig1_l, sig1_s = count_entry_signals(df1)
            sig5_l, sig5_s = count_entry_signals(df5)
            current_count = max(sig1_l, sig1_s) + max(sig5_l, sig5_s)

            if current_count < initial_count:
                actual_amt = get_open_position_amt(sym)
                _, _, min_qty = get_precision(sym)

                # 50% 익절
                if current_count == initial_count - 1:
                    take_amt = (Decimal(str(actual_amt)) * Decimal("0.5")).quantize(quant, rounding=ROUND_DOWN)
                    if take_amt > 0:
                        create_market_order(
                            sym,
                            "SELL" if side == "long" else "BUY",
                            float(take_amt),
                            reduceOnly=True
                        )
                # 90% 익절
                elif current_count <= initial_count - 2:
                    take_amt = (Decimal(str(actual_amt)) * Decimal("0.9")).quantize(quant, rounding=ROUND_DOWN)
                    if take_amt > 0:
                        create_market_order(
                            sym,
                            "SELL" if side == "long" else "BUY",
                            float(take_amt),
                            reduceOnly=True
                        )

                # 남은 잔량이 최소수량 미만이면 전량 시장가 청산
                remaining_amt = get_open_position_amt(sym)
                if 0 < remaining_amt < min_qty:
                    create_market_order(
                        sym,
                        "SELL" if side == "long" else "BUY",
                        float(remaining_amt),
                        reduceOnly=True
                    )

            time.sleep(0.1)
    except Exception as e:
        logging.error(f"{sym} 모니터링 오류: {e}")

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

            # 배치 호출 최적화 (추후 비동기 개선 가능)
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

                # 보조 지표
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

                # 진입 실행
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

                # 동적 LIMIT_ORDER_WAIT (ATR 기반 예시)
                atr_series = calculate_atr(df1, length=14)
                atr = atr_series.iloc[-1] if atr_series is not None and not np.isnan(atr_series.iloc[-1]) else None
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
                    order_info = client.futures_get_order(symbol=sym, orderId=order_id)
                except Exception:
                    cancel_all_orders_for_symbol(sym)
                    continue

                if order_info.get('status') != 'FILLED':
                    cancel_all_orders_for_symbol(sym)
                    continue

                fills = order_info.get('fills')
                entry_price = Decimal(str(fills[0]['price'])) if fills else Decimal(str(mark_price))

                # TP/SL 설정 (SL 실패 시, TP_RATIO 기반 SL 재설정 → 여전히 실패하면 1% SL 고정)
                if primary_sig == 'long':
                    tp = (entry_price * (Decimal("1") + TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    base_sl = (entry_price * (Decimal("1") - SL_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    sl = max(base_sl, entry_price - tick_size * 2)

                    # TP 주문
                    tp_ord = create_take_profit(sym, 'SELL', float(tp), float(qty))

                    # SL 주문 시도
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

                    # TP 주문
                    tp_ord = create_take_profit(sym, 'BUY', float(tp), float(qty))

                    # SL 주문 시도
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
    except:
        pass
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
        sys.exit(0)
