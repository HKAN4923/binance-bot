# main.py

import sys
import numpy as np
import time
import threading
import logging
from decimal import Decimal, ROUND_DOWN
import pandas as pd

from config import (
    MAX_POSITIONS,
    ANALYSIS_INTERVAL_SEC,
    LEVERAGE
)
from utils import (
    to_kst,
    calculate_qty,
    get_top_100_volume_symbols,
    get_tradable_futures_symbols,
    get_tick_size
)
from telegram_notifier import send_telegram
from trade_summary import start_summary_scheduler
from position_monitor import PositionMonitor
from strategy import check_entry_multi, calculate_ema_cross, calculate_rsi
from binance_client import (
    client,
    get_ohlcv,
    get_balance,
    get_mark_price,
    get_precision,
    create_market_order,
    create_stop_order,
    create_take_profit,
    create_limit_order,
    cancel_all_orders_for_symbol,
    get_open_position_amt,
)

# ─────────────────────────────────────────────────────────────────────────────
# 전역 변수
wins = 0
losses = 0

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# 진입 관련 상수
PRIMARY_THRESHOLD = 2       # 1m/5m 지표 최소 일치 개수
AUX_COUNT_THRESHOLD = 2     # 보조지표 최소 일치 개수
EMA_SHORT_LEN = 20          # 30m EMA 단기
EMA_LONG_LEN = 50           # 30m EMA 장기
VOLUME_SPIKE_MULTIPLIER = 2  # 거래량 스파이크 임계값

# TP/SL 고정 비율 (TP: 1.75% / SL: 0.8%)
TP_RATIO = Decimal("0.0175")
SL_RATIO = Decimal("0.008")

# PnL 기준 (–0.5%, +0.5%)
PIL_LOSS_THRESHOLD = Decimal("0.005")
PIL_PROFIT_THRESHOLD = Decimal("0.005")

# 리미트 주문 대기 시간 (초)
LIMIT_ORDER_WAIT = 6

# 추정 리미트 진입 편차 (0.2% favorable)
LIMIT_OFFSET = Decimal("0.0015")

# ─────────────────────────────────────────────────────────────────────────────

# 메모리 상 포지션 기록
#각 심볼별로 다음 정보를 저장:
# { 'side', 'quantity', 'entry_price', 'initial_match_count', 'primary_sig', 'start_time', 'tp_order_id', 'sl_order_id' }
positions = {}
positions_lock = threading.Lock()

# 누적 거래 내역 로그
trade_log = []
trade_log_lock = threading.Lock()


def count_open_positions():
    """
    positions 딕셔너리에 기록된 심볼 중에서
    실제 바이낸스에 포지션이 남아있는(symbolAmt != 0) 개수를 셉니다.
    포지션이 없어졌을 때는 메모리에서도 자동으로 제거합니다.
    """
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
            sys.exit(1)
    return cnt


def compute_obv_signal(df: pd.DataFrame):
    """
    OBV 기반 신호
    """
    try:
        df = df.copy()
        df['change'] = df['close'].diff()
        df['vol_adj'] = df['volume'].where(df['change'] > 0, -df['volume'])
        df['obv'] = df['vol_adj'].cumsum()
        last_obv = df['obv'].iloc[-1]
        prev_obv = df['obv'].iloc[-2]
        if last_obv > prev_obv:
            return "long"
        elif last_obv < prev_obv:
            return "short"
        return None
    except Exception as e:
        logging.error(f"Error in compute_obv_signal: {e}")
        sys.exit(1)


def compute_volume_spike_signal(df: pd.DataFrame):
    """
    거래량 스파이크 기반 신호
    """
    try:
        df = df.copy()
        if len(df) < 21:
            return None
        prev_vols = df['volume'].iloc[-21:-1]
        mean_prev_vol = prev_vols.mean()
        last_vol = df['volume'].iloc[-1]
        last_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        if mean_prev_vol and last_vol > mean_prev_vol * VOLUME_SPIKE_MULTIPLIER:
            if last_close > prev_close:
                return "long"
            elif last_close < prev_close:
                return "short"
        return None
    except Exception as e:
        logging.error(f"Error in compute_volume_spike_signal: {e}")
        sys.exit(1)


def compute_bollinger_signal(df: pd.DataFrame):
    """
    볼린저 밴드 기반 신호
    """
    try:
        if len(df) < 20:
            return None
        df = df.copy()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['upper'] = df['sma20'] + 2 * df['std20']
        df['lower'] = df['sma20'] - 2 * df['std20']
        last_close = df['close'].iloc[-1]
        last_upper = df['upper'].iloc[-1]
        last_lower = df['lower'].iloc[-1]
        if last_close > last_upper:
            return "long"
        elif last_close < last_lower:
            return "short"
        return None
    except Exception as e:
        logging.error(f"Error in compute_bollinger_signal: {e}")
        sys.exit(1)


def count_entry_signals(df: pd.DataFrame):
    """
    5개 지표(RSI, MACD 히스토그램, EMA20/50, Stochastic, ADX) 중
    long/short 신호 개수 반환
    """
    try:
        # 1) RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=9).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=9).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        rsi_signal = None
        if prev_rsi < 35 and last_rsi > 35:
            rsi_signal = "long"
        elif prev_rsi > 65 and last_rsi < 65:
            rsi_signal = "short"

        # 2) MACD 히스토그램
        ema_fast = df['close'].ewm(span=8, adjust=False).mean()
        ema_slow = df['close'].ewm(span=17, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        last_hist = hist.iloc[-1]
        prev_hist = hist.iloc[-2]
        macd_signal = None
        if prev_hist < 0 and last_hist > 0:
            macd_signal = "long"
        elif prev_hist > 0 and last_hist < 0:
            macd_signal = "short"

        # 3) EMA20/50 교차
        df['_ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['_ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        last_ema20 = df['_ema20'].iloc[-1]
        prev_ema20 = df['_ema20'].iloc[-2]
        last_ema50 = df['_ema50'].iloc[-1]
        prev_ema50 = df['_ema50'].iloc[-2]
        ema_signal = None
        if prev_ema20 < prev_ema50 and last_ema20 > last_ema50:
            ema_signal = "long"
        elif prev_ema20 > prev_ema50 and last_ema20 < last_ema50:
            ema_signal = "short"

        # 4) Stochastic
        low_min = df['low'].rolling(9).min()
        high_max = df['high'].rolling(9).max()
        df['%K'] = (df['close'] - low_min) / (high_max - low_min) * 100
        df['%D'] = df['%K'].rolling(3).mean()
        last_K = df['%K'].iloc[-1]
        prev_K = df['%K'].iloc[-2]
        last_D = df['%D'].iloc[-1]
        prev_D = df['%D'].iloc[-2]
        stoch_signal = None
        if prev_K < 20 and last_K > 20 and last_K > last_D:
            stoch_signal = "long"
        elif prev_K > 80 and last_K < 80 and last_K < last_D:
            stoch_signal = "short"

        # 5) ADX + DI
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        df['+DM'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0.0)
        df['-DM'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0.0)
        df['TR'] = np.maximum.reduce([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        ])
        atr = df['TR'].rolling(10).mean()
        df['+DI'] = (df['+DM'] / atr) * 100
        df['-DI'] = (df['-DM'] / atr) * 100
        df['DX'] = (df['+DI'] - df['-DI']).abs() / (df['+DI'] + df['-DI']) * 100
        df['ADX'] = df['DX'].rolling(10).mean()
        last_plus = df['+DI'].iloc[-1]
        last_minus = df['-DI'].iloc[-1]
        last_adx = df['ADX'].iloc[-1]
        adx_signal = None
        if last_adx > 20 and last_plus > last_minus:
            adx_signal = "long"
        elif last_adx > 20 and last_minus > last_plus:
            adx_signal = "short"

        signals = [rsi_signal, macd_signal, ema_signal, stoch_signal, adx_signal]
        long_count = sum(1 for s in signals if s == "long")
        short_count = sum(1 for s in signals if s == "short")
        return long_count, short_count
    except Exception as e:
        logging.error(f"Error in count_entry_signals: {e}")
        sys.exit(1)


def compute_rebound_signal(symbol: str) -> bool:
    """
    PnL < -0.5% 일 때, 반등 신호 감지 (RSI 기준).
    1분봉 RSI < 30에서 > 30으로 전환되면 반등으로 간주.
    """
    try:
        df1 = get_ohlcv(symbol, '1m', limit=50)
        if df1 is None or len(df1) < 50:
            return False
        calculate_rsi(df1)
        last_rsi = df1['rsi'].iloc[-1]
        prev_rsi = df1['rsi'].iloc[-2]
        return prev_rsi < 30 and last_rsi > 30
    except Exception as e:
        logging.error(f"Error in compute_rebound_signal: {e}")
        sys.exit(1)


def compute_drop_signal(symbol: str) -> bool:
    """
    PnL > +0.5% 일 때, 하락 신호 감지 (RSI 기준).
    1분봉 RSI > 70에서 < 70으로 전환되면 하락으로 간주.
    """
    try:
        df1 = get_ohlcv(symbol, '1m', limit=50)
        if df1 is None or len(df1) < 50:
            return False
        calculate_rsi(df1)
        last_rsi = df1['rsi'].iloc[-1]
        prev_rsi = df1['rsi'].iloc[-2]
        return prev_rsi > 70 and last_rsi < 70
    except Exception as e:
        logging.error(f"Error in compute_drop_signal: {e}")
        sys.exit(1)


def cleanup_orphan_orders():
    """
    10초마다 실행: 열려있는 TP/SL 주문 중 positions에 없는 심볼의 주문 삭제.
    """
    while True:
        try:
            open_orders = client.futures_get_open_orders()
            symbols_with_orders = set(o['symbol'] for o in open_orders)
            with positions_lock:
                tracked = set(positions.keys())
            for sym in symbols_with_orders:
                if sym not in tracked:
                    cancel_all_orders_for_symbol(sym)
                    logging.info(f"{sym} - positions에 없음 → 열린 주문 삭제")
            time.sleep(10)
        except Exception as e:
            logging.error(f"cleanup_orphan_orders 오류: {e}")
            sys.exit(1)


def monitor_position(sym):
    """
    진입 후 10초 간격으로 지표를 재확인하여 단계별 익절/청산 및 PnL 기반 추가 로직 처리.
    1초마다 긴급 탈출 조건은 PositionMonitor가 담당.
    """
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

        # 심볼의 quantity precision 조회
        _, qty_precision, _ = get_precision(sym)
        quant = Decimal(f"1e-{qty_precision}")

        while True:
            time.sleep(10)  # 10초마다 확인

            # 이미 포지션이 닫혔으면 종료
            amt = get_open_position_amt(sym)
            if amt == 0:
                break

            # 현재 PnL 계산 (entry_price와 mark_price 기반)
            mark_price = Decimal(str(get_mark_price(sym)))
            if primary_sig == "long":
                pnl = (mark_price - entry_price) / entry_price
            else:
                pnl = (entry_price - mark_price) / entry_price

            # 1) PnL < –0.5%: 반등 신호 없으면 전량 청산
            if pnl < -PIL_LOSS_THRESHOLD:
                if not compute_rebound_signal(sym):
                    create_market_order(sym, "SELL" if side == "BUY" else "BUY", float(quantity), reduceOnly=True)
                    with positions_lock:
                        positions.pop(sym, None)
                    msg = (
                        f"<b>🔸 STOP CLOSE (No Rebound): {sym}</b>\n"
                        f"▶ 방향: {primary_sig.upper()}\n"
                        f"▶ PnL: {pnl * 100:.2f}%\n"
                        f"▶ 전체 기록: {wins}승 {losses}패"
                    )
                    send_telegram(msg)
                    break  # 모니터 종료
                else:
                    continue  # 반등 감지 시 유지

            # 2) PnL > +0.5%: 하락 신호 있으면 전량 청산
            if pnl > PIL_PROFIT_THRESHOLD:
                if compute_drop_signal(sym):
                    create_market_order(sym, "SELL" if side == "BUY" else "BUY", float(quantity), reduceOnly=True)
                    with positions_lock:
                        positions.pop(sym, None)
                    msg = (
                        f"<b>🔸 TAKE CLOSE (Drop Signal): {sym}</b>\n"
                        f"▶ 방향: {primary_sig.upper()}\n"
                        f"▶ PnL: {pnl * 100:.2f}%\n"
                        f"▶ 전체 기록: {wins}승 {losses}패"
                    )
                    send_telegram(msg)
                    break  # 모니터 종료
                else:
                    # 하락 신호 없으면 유지
                    pass

            # ────────────────────────────────────────────────────────────────────
            # 기존 부분 익절/청산 로직 (수정된 부분)
            # ────────────────────────────────────────────────────────────────────

            df1 = get_ohlcv(sym, '1m', limit=50)
            time.sleep(0.1)
            df5 = get_ohlcv(sym, '5m', limit=50)
            time.sleep(0.1)
            if df1 is None or df5 is None:
                continue

            sig1_long, sig1_short = count_entry_signals(df1)
            sig5_long, sig5_short = count_entry_signals(df5)
            current_count = max(sig1_long, sig1_short) + max(sig5_long, sig5_short)

            # 1) 신호 그대로 유지 → 아무 조치 없음
            if current_count == initial_count:
                continue

            # 2) 신호가 1만큼 줄었으면 50% 익절
            if current_count == initial_count - 1:
                raw_qty = quantity * Decimal("0.5")
                take_qty = raw_qty.quantize(quant, rounding=ROUND_DOWN)

                # 현재 포지션 수량 확인 후 조정
                actual_amt = get_open_position_amt(sym)
                if take_qty > actual_amt:
                    take_qty = actual_amt

                if take_qty > 0:
                    create_market_order(sym, "SELL" if side == "BUY" else "BUY", float(take_qty), reduceOnly=True)
                    logging.info(f"{sym} 50% 익절 주문: {take_qty}")
                continue

            # 3) 신호가 2 이상 줄었으면 90% 익절
            if current_count <= initial_count - 2:
                raw_qty = quantity * Decimal("0.9")
                take_qty = raw_qty.quantize(quant, rounding=ROUND_DOWN)

                # 현재 포지션 수량 확인 후 조정
                actual_amt = get_open_position_amt(sym)
                if take_qty > actual_amt:
                    take_qty = actual_amt

                if take_qty > 0:
                    create_market_order(sym, "SELL" if side == "BUY" else "BUY", float(take_qty), reduceOnly=True)
                    logging.info(f"{sym} 90% 익절 주문: {take_qty}")
                continue

            # 4) 신호 방향이 바뀌면 전량 청산
            primary_now = None
            if sig1_long and not sig5_long:
                primary_now = "long"
            elif sig5_long and not sig1_long:
                primary_now = "long"
            elif sig1_long and sig5_long and sig1_long == sig5_long:
                primary_now = "long" if sig1_long > sig1_short else "short"

            if primary_now and primary_now != primary_sig:
                actual_amt = get_open_position_amt(sym)
                if actual_amt > 0:
                    create_market_order(sym, "SELL" if side == "BUY" else "BUY", float(actual_amt), reduceOnly=True)
                    logging.info(f"{sym} 신호 반전 전량 청산 주문: {actual_amt}")
                    msg = (
                        f"<b>🔸 SIGNAL REVERSE EXIT: {sym}</b>\n"
                        f"▶ 방향: {primary_sig.upper()} → {primary_now.upper()}\n"
                        f"▶ 전체 기록: {wins}승 {losses}패"
                    )
                    send_telegram(msg)
                break  # 모니터 종료

            # 다음 10초 대기

    except Exception as e:
        logging.error(f"{sym} 모니터링 오류: {e}")
        sys.exit(1)


def analyze_market():
    """
    - ANALYSIS_INTERVAL_SEC마다 시장 분석
    - 30분마다 tradable_symbols 갱신 (24h 상위 100개 심볼)
    """
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

            # 포지션 개수 확인
            current_positions = count_open_positions()
            now = to_kst(time.time())
            logging.info(f"{now.strftime('%H:%M:%S')} 📊 분석중. (실제 포지션 {current_positions}/{MAX_POSITIONS})")

            # 최대 포지션 수 초과 시 대기
            if current_positions >= MAX_POSITIONS:
                time.sleep(ANALYSIS_INTERVAL_SEC)
                continue

            for sym in tradable_symbols:
                # 매 심볼 진입 전 포지션 개수 다시 확인
                if count_open_positions() >= MAX_POSITIONS:
                    break

                # 메모리 상 이미 기록된 심볼 건너뛰기
                with positions_lock:
                    if sym in positions:
                        continue

                # 1m, 5m 데이터 조회
                df1 = get_ohlcv(sym, '1m', limit=50)
                time.sleep(0.1)
                df5 = get_ohlcv(sym, '5m', limit=50)
                time.sleep(0.1)

                if df1 is None or len(df1) < 50 or df5 is None or len(df5) < 50:
                    continue

                sig1 = check_entry_multi(df1, threshold=PRIMARY_THRESHOLD)
                sig5 = check_entry_multi(df5, threshold=PRIMARY_THRESHOLD)

                primary_sig = None
                primary_tf = None
                if sig1 and not sig5:
                    primary_sig = sig1
                    primary_tf = '1m'
                elif sig5 and not sig1:
                    primary_sig = sig5
                    primary_tf = '5m'
                elif sig1 and sig5 and sig1 == sig5:
                    primary_sig = sig1
                    primary_tf = 'both'
                else:
                    continue

                # 보조지표 OR 로직
                aux_signals = []
                df30 = get_ohlcv(sym, '30m', limit=EMA_LONG_LEN + 2)
                if df30 is not None and len(df30) >= EMA_LONG_LEN:
                    calculate_ema_cross(df30, short_len=EMA_SHORT_LEN, long_len=EMA_LONG_LEN)
                    last_ema_short = df30[f"_ema{EMA_SHORT_LEN}"].iloc[-1]
                    last_ema_long = df30[f"_ema{EMA_LONG_LEN}"].iloc[-1]
                    if last_ema_short > last_ema_long:
                        aux_signals.append("long")
                    elif last_ema_short < last_ema_long:
                        aux_signals.append("short")

                obv_sig = compute_obv_signal(df1)
                if obv_sig:
                    aux_signals.append(obv_sig)

                vol_sig = compute_volume_spike_signal(df1)
                if vol_sig:
                    aux_signals.append(vol_sig)

                bb_sig = compute_bollinger_signal(df1)
                if bb_sig:
                    aux_signals.append(bb_sig)

                match_count = sum(1 for s in aux_signals if s == primary_sig)
                if match_count < AUX_COUNT_THRESHOLD:
                    continue

                # ───────────────────────────────────────────────────
                # 진입 조건 충족 시 진입 블럭
                # ───────────────────────────────────────────────────

                # Step 1: 잔고, 현재가, 레버리지, 수량 계산
                balance = get_balance()
                mark_price = get_mark_price(sym)
                price_precision, qty_precision, min_qty = get_precision(sym)
                sig1_long, sig1_short = count_entry_signals(df1)
                sig5_long, sig5_short = count_entry_signals(df5)
                initial_count = max(sig1_long, sig1_short) + max(sig5_long, sig5_short)

                side = "BUY" if primary_sig == "long" else "SELL"
                direction_kr = "롱" if primary_sig == "long" else "숏"
                qty = calculate_qty(
                    balance,
                    Decimal(str(mark_price)),
                    LEVERAGE,
                    Decimal("0.3"),
                    qty_precision,
                    min_qty
                )
                if qty == 0 or qty < Decimal(str(min_qty)):
                    continue

                # Step 2: 리미트 진입 설정 (0.2% 유리한 가격)
                quant_price = Decimal(f"1e-{price_precision}")
                tick_size = get_tick_size(sym)
                if side == "BUY":  # 롱
                    limit_price_dec = (Decimal(str(mark_price)) * (Decimal("1") - LIMIT_OFFSET)).quantize(quant_price, ROUND_DOWN)
                else:  # 숏
                    limit_price_dec = (Decimal(str(mark_price)) * (Decimal("1") + LIMIT_OFFSET)).quantize(quant_price, ROUND_DOWN)

                limit_price = float(limit_price_dec)
                try:
                    entry_order = create_limit_order(
                        sym,
                        side,
                        float(qty),
                        limit_price
                    )
                except Exception as e:
                    logging.error(f"{sym} 리미트 주문 오류: {e}")
                    continue

                order_id = entry_order.get('orderId')
                # Step 3: LIMIT_ORDER_WAIT초 대기
                time.sleep(LIMIT_ORDER_WAIT)
                try:
                    order_info = client.futures_get_order(symbol=sym, orderId=order_id)
                except Exception as e:
                    logging.error(f"{sym} 주문 조회 오류: {e}")
                    cancel_all_orders_for_symbol(sym)
                    continue

                if order_info.get('status') != 'FILLED':
                    # 체결 안 됐으면 주문 취소 후 다음 심볼로
                    cancel_all_orders_for_symbol(sym)
                    logging.info(f"{sym} 리미트 미체결 → 주문 취소, 진입 취소")
                    continue

                # 체결된 경우 entry_price 확정
                fills = order_info.get('fills')
                if fills:
                    entry_price = Decimal(str(fills[0]['price']))
                else:
                    entry_price = Decimal(str(mark_price))

                # Step 4: TP/SL 설정 (tick_size 보정 포함)
                if primary_sig == "long":
                    tp_price = (entry_price * (Decimal("1") + TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    base_sl = (entry_price * (Decimal("1") - SL_RATIO)).quantize(quant_price, ROUND_DOWN)
                    sl_price = max(base_sl, entry_price - tick_size * 2)
                    tp_order = create_take_profit(sym, "SELL", float(tp_price), float(qty))
                    sl_order = create_stop_order(sym, "SELL", float(sl_price), float(qty))
                else:
                    tp_price = (entry_price * (Decimal("1") - TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                    base_sl = (entry_price * (Decimal("1") + SL_RATIO)).quantize(quant_price, ROUND_DOWN)
                    sl_price = min(base_sl, entry_price + tick_size * 2)
                    tp_order = create_take_profit(sym, "BUY", float(tp_price), float(qty))
                    sl_order = create_stop_order(sym, "BUY", float(sl_price), float(qty))

                tp_id = tp_order.get('orderId') if tp_order else None
                sl_id = sl_order.get('orderId') if sl_order else None

                # Step 5: 메모리 저장
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
                logging.info(f"✅ {sym} 포지션 저장 완료 → 메모리 상 현재 {len(positions)}개, 실제 {count_open_positions()}개")

                # Step 6: 진입 알림
                logging.info(f"{sym} ({direction_kr}/{initial_count}) 진입 완료 → entry_price={entry_price:.4f}, TP={tp_price}, SL={sl_price}")
                msg = (
                    f"<b>🔹 ENTRY: {sym}</b>\n"
                    f"▶ 방향: {primary_sig.upper()} (TF: {primary_tf})\n"
                    f"▶ 초기 신호 개수: {initial_count}\n"
                    f"▶ 진입가: {entry_price:.4f}\n"
                    f"▶ TP: {tp_price}\n"
                    f"▶ SL: {sl_price}"
                )
                send_telegram(msg)

                # Step 7: 모니터 스레드 시작
                threading.Thread(target=monitor_position, args=(sym,), daemon=True).start()

                # 최대 포지션 도달하면 루프 중단
                time.sleep(0.05)
                if count_open_positions() >= MAX_POSITIONS:
                    break

            time.sleep(ANALYSIS_INTERVAL_SEC)

        except Exception as e:
            logging.error(f"Error in analyze_market: {e}")
            sys.exit(1)


def close_callback(symbol, side, pnl_pct, pnl_usdt):
    """
    포지션 청산 콜백. 터미널과 텔레그램에 한 줄 요약만 남김
    """
    global wins, losses
    if pnl_pct > 0:
        wins += 1
    else:
        losses += 1

    direction_kr = '롱' if side == 'long' else '숏'
    logging.info(f"{symbol} 청산 ({direction_kr}/{pnl_usdt:.2f}USDT,{pnl_pct * 100:.2f}%)")

    msg = (
        f"<b>🔸 EXIT: {symbol}</b>\n"
        f"▶ 방향: {direction_kr}\n"
        f"▶ 실현 손익: {pnl_usdt:.2f} USDT ({pnl_pct * 100:.2f}%)\n"
        f"▶ 전체 기록: {wins}승 {losses}패"
    )
    send_telegram(msg)


if __name__ == "__main__":
    # 봇 시작 알림
    try:
        send_telegram("<b>🤖 자동매매 봇이 시작되었습니다!</b>")
    except Exception as e:
        logging.error(f"봇 시작 텔레그램 전송 오류: {e}")
        sys.exit(1)
    logging.info("자동매매 봇 시작 알림 전송 완료")

    # Trade Summary 스케줄러
    start_summary_scheduler(trade_log, trade_log_lock)
    logging.info("Trade Summary 스케줄러 시작 완료")

    # PositionMonitor 스레드 시작 (1초마다 긴급 탈출 체크)
    pos_monitor = PositionMonitor(positions, positions_lock, trade_log, trade_log_lock, close_callback)
    pos_monitor.start()
    logging.info("PositionMonitor 스레드 시작 완료")

    # Cleanup orphan orders 스레드 시작
    threading.Thread(target=cleanup_orphan_orders, daemon=True).start()
    logging.info("Orphan orders cleanup 스레드 시작 완료")

    # Analyze Market 스레드 시작
    threading.Thread(target=analyze_market, daemon=True).start()
    logging.info("Analyze Market 스레드 시작 완료")

    try:
        while True:
            logging.info("⏳ 봇 정상 대기 중... (main loop idle)")
            time.sleep(30)
    except Exception as e:
        logging.error(f"메인 루프 오류: {e}")
        sys.exit(1)
