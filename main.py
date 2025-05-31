# main.py

import numpy as np
from config import (
    MAX_POSITIONS,
    ANALYSIS_INTERVAL_SEC,
    LEVERAGE,
    FIXED_PROFIT_TARGET,
    FIXED_LOSS_CAP_BASE,
    MIN_SL,
    PARTIAL_EXIT_RATIO,
    PARTIAL_TARGET_RATIO,
    RECHECK_START,
    RECHECK_INTERVAL,
    MAX_TRADE_DURATION
)
from utils import to_kst, calculate_qty
from telegram_notifier import send_telegram
from trade_summary import start_summary_scheduler
from position_monitor import PositionMonitor
from strategy import check_entry_multi, calculate_ema_cross
from binance_client import (
    client,
    get_ohlcv,
    get_balance,
    get_mark_price,
    get_precision,
    create_market_order,
    create_take_profit,
    create_stop_order,
    cancel_all_orders_for_symbol
)
import time
import threading
import logging
from decimal import Decimal
import operator

import pandas as pd
wins = 0
losses = 0


# ─────────────────────────────────────────────────────────────────────────────
# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ─────────────────────────────────────────────────────────────────────────────
# 진입 관련 상수
PRIMARY_THRESHOLD = 2          # 1분봉 또는 5분봉 지표 최소 개수
AUX_COUNT_THRESHOLD = 2        # 보조지표 최소 개수
EMA_SHORT_LEN = 20             # 30분봉 EMA 단기
EMA_LONG_LEN = 50              # 30분봉 EMA 장기
VOLUME_SPIKE_MULTIPLIER = 2     # 거래량 스파이크 임계값

# ─────────────────────────────────────────────────────────────────────────────


def get_tradable_futures_symbols():
    """
    바이낸스 전체 USDT 페어 무기한 선물 중
    - status == 'TRADING'
    - marginAsset == 'USDT'
    - contractType == 'PERPETUAL'
    - isTradingAllowed == True
    만 필터링하여 리스트 반환
    """
    try:
        exchange_info = client.futures_exchange_info()
        tradable = []
        for s in exchange_info['symbols']:
            if (
                s.get('contractType') == 'PERPETUAL'
                and s.get('status') == 'TRADING'
                and s.get('marginAsset') == 'USDT'
                and s.get('symbol', '').endswith('USDT')
                and s.get('isTradingAllowed', True)
            ):
                tradable.append(s['symbol'])
        return tradable
    except Exception as e:
        logging.error(f"Error in get_tradable_futures_symbols: {e}")
        return []


def get_top_100_volume_symbols():
    """
    바이낸스 선물 마켓에서 24시간 거래량(quoteVolume) 기준 상위 100개 USDT 심볼 반환
    """
    try:
        stats_24hr = client.futures_ticker()
        usdt_pairs = [
            {'symbol': s['symbol'], 'volume': float(s['quoteVolume'])}
            for s in stats_24hr
            if s['symbol'].endswith('USDT') and s['symbol'].isupper()
        ]
        usdt_pairs.sort(key=lambda x: x['volume'], reverse=True)
        top_100 = [item['symbol'] for item in usdt_pairs[:100]]
        return top_100
    except Exception as e:
        logging.error(f"Error in get_top_100_volume_symbols: {e}")
        return []


def compute_tp_sl(atr_pct: Decimal):
    """
    ATR 기반 동적 TP/SL 계산
    """
    tp_pct_dyn = atr_pct * Decimal("1.8")
    sl_pct_dyn = atr_pct * Decimal("1.2")

    tp_pct = min(tp_pct_dyn, FIXED_PROFIT_TARGET)
    sl_pct = min(max(sl_pct_dyn, MIN_SL), FIXED_LOSS_CAP_BASE)

    return tp_pct, sl_pct


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
        return None


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
        return None


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
        return None


def count_entry_signals(df: pd.DataFrame):
    """
    check_entry_multi와 동일한 5개 지표 로직에서
    ‘long’/’short’ 신호를 낸 개수를 (long_count, short_count) 형태로 반환.
    """
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
    df['+DM'] = np.where((df['up_move'] > df['down_move'])
                         & (df['up_move'] > 0), df['up_move'], 0.0)
    df['-DM'] = np.where((df['down_move'] > df['up_move'])
                         & (df['down_move'] > 0), df['down_move'], 0.0)
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


def analyze_market():
    """
    - ANALYSIS_INTERVAL_SEC마다 시장 분석
    - 30분마다 tradable_symbols 목록을 갱신하되, ‘24h 거래량 상위 100개 심볼’만 사용
    """
    tradable_symbols = []
    last_update = 0

    while True:
        try:
            now_ts = time.time()
            if now_ts - last_update > 1800 or not tradable_symbols:
                tradable_symbols = get_top_100_volume_symbols()
                last_update = now_ts
                if tradable_symbols:
                    logging.info(
                        f"유효 심볼 리스트 갱신 → 24h 상위 100개 거래량 심볼 사용: 총 {len(tradable_symbols)}개")
                    logging.debug(f"Top5 샘플: {tradable_symbols[:5]}")
                else:
                    tradable_symbols = get_tradable_futures_symbols()
                    logging.warning(
                        "get_top_100_volume_symbols() 실패 → 전체 tradable 심볼 사용")

            now = to_kst(time.time())
            with positions_lock:
                current_positions = len(positions)
            logging.info(
                f"{now.strftime('%H:%M:%S')} 📊 분석중... (포지션 {current_positions}/{MAX_POSITIONS})")

            if current_positions < MAX_POSITIONS:
                for sym in tradable_symbols:
                    with positions_lock:
                        if sym in positions:
                            continue

                    df1 = get_ohlcv(sym, '1m', limit=50)
                    time.sleep(0.1)
                    df5 = get_ohlcv(sym, '5m', limit=50)
                    time.sleep(0.1)

                    if df1 is None or len(df1) < 50:
                        logging.warning(
                            f"{sym} 1분봉 데이터 부족/오류 → df1 is None or len<50")
                        continue
                    if df5 is None or len(df5) < 50:
                        logging.warning(
                            f"{sym} 5분봉 데이터 부족/오류 → df5 is None or len<50")
                        continue

                    sig1 = check_entry_multi(df1, threshold=PRIMARY_THRESHOLD)
                    sig5 = check_entry_multi(df5, threshold=PRIMARY_THRESHOLD)

                    primary_sig = None
                    primary_tf = None
                    if sig1 and not sig5:
                        primary_sig = sig1; primary_tf = '1m'
                    elif sig5 and not sig1:
                        primary_sig = sig5; primary_tf = '5m'
                    elif sig1 and sig5 and sig1 == sig5:
                        primary_sig = sig1; primary_tf = 'both'
                    else:
                        logging.debug(
                            f"{sym} primary 신호 불충분 or 상반됨 → sig1={sig1}, sig5={sig5}")
                        continue

                    # logging.info(f"{sym} primary 신호: {primary_sig} (TF={primary_tf})")

                    # 보조지표 OR
                    aux_signals = []

                    df30 = get_ohlcv(sym, '30m', limit=EMA_LONG_LEN + 2)
                    if df30 is None or len(df30) < EMA_LONG_LEN:
                        logging.warning(
                            f"{sym} 30분봉 데이터 부족/오류 → df30 is None or len<{EMA_LONG_LEN}")
                    else:
                        calculate_ema_cross(
                            df30, short_len=EMA_SHORT_LEN, long_len=EMA_LONG_LEN)
                        last_ema_short = df30[f"_ema{EMA_SHORT_LEN}"].iloc[-1]
                        last_ema_long = df30[f"_ema{EMA_LONG_LEN}"].iloc[-1]
                        if last_ema_short > last_ema_long:
                            aux_signals.append("long")
                        elif last_ema_short < last_ema_long:
                            aux_signals.append("short")
                       # logging.debug(f"{sym} EMA30 신호: {'long' if last_ema_short>last_ema_long else 'short' if last_ema_short<last_ema_long else '없음'}")

                    obv_sig = compute_obv_signal(df1)
                    if obv_sig: aux_signals.append(obv_sig)
                   # logging.debug(f"{sym} OBV 신호: {obv_sig}")

                    vol_sig = compute_volume_spike_signal(df1)
                    if vol_sig: aux_signals.append(vol_sig)
                  #  logging.debug(f"{sym} 거래량 스파이크 신호: {vol_sig}")

                    bb_sig = compute_bollinger_signal(df1)
                    if bb_sig: aux_signals.append(bb_sig)
                   # logging.debug(f"{sym} 볼린저 밴드 신호: {bb_sig}")

                    match_count = sum(
                        1 for s in aux_signals if s == primary_sig)
                    if match_count < AUX_COUNT_THRESHOLD:
                        # logging.debug(f"{sym} 보조지표 충족 못 함 → match_count={match_count}/{AUX_COUNT_THRESHOLD}")
                        continue

    # ② 방향을 한국어 ‘롱’/‘숏’으로 바꿔서 찍기
                    direction_kr = '롱' if primary_sig == 'long' else '숏'
                    tp_pct_str = f"{tp_pct * 100:.2f}%"
                    sl_pct_str = f"{sl_pct * 100:.2f}%"

                    logging.info(
                        f"{sym} ({direction_kr}/{sig1_count},{sig5_count},{aux_count}/"
                        f"{tp_pct_str},{sl_pct_str})"
                )

                   # 진입 조건이 충족되었을 때만 아래 실행됨
# match_count >= AUX_COUNT_THRESHOLD 상태


# Step 1: 진입 수량 계산을 위한 정보 수집
balance = get_balance()
mark_price = get_mark_price(sym)
price_precision, qty_precision, min_qty = get_precision(sym)

# Step 2: ATR 계산 → TP/SL 비율 계산
last_row = df5.iloc[-1]
high = Decimal(str(last_row['high']))
low = Decimal(str(last_row['low']))
close = Decimal(str(last_row['close']))
atr_pct = (high - low) / close
tp_pct, sl_pct = compute_tp_sl(atr_pct)  # ✅ 이걸 먼저 해야 tp_pct 사용 가능!

# Step 3: 신호 개수 계산 (진입 근거용)
sig1_long, sig1_short = count_entry_signals(df1)
sig5_long, sig5_short = count_entry_signals(df5)
sig1_count = max(sig1_long, sig1_short)
sig5_count = max(sig5_long, sig5_short)
aux_count = match_count

# Step 4: 진입 방향
side = "BUY" if primary_sig == "long" else "SELL"
direction_kr = "롱" if primary_sig == "long" else "숏"

# Step 5: 수량 계산
qty = calculate_qty(balance, Decimal(str(mark_price)),
                    LEVERAGE, Decimal("1"), qty_precision, min_qty)
if qty == 0 or qty < Decimal(str(min_qty)):
    return

# Step 6: ✅ 터미널 로그 출력 (tp_pct/sl_pct는 이제 정의된 상태)
logging.info(
    f"{sym} ({direction_kr}/{sig1_count},{sig5_count},{aux_count}/"
    f"{tp_pct * 100:.2f}%,{sl_pct * 100:.2f}%)"
)

# Step 7: 시장가 진입
entry_order = create_market_order(sym, side, qty)
if entry_order is None:
    return

# Step 8: 진입가 추정
entry_price = get_entry_price(entry_order, mark_price)

# Step 9: TP/SL 가격 계산 및 주문
tp_price, sl_price = get_tp_sl_prices(entry_price, tp_pct, sl_pct, side)
create_take_profit(sym, side, qty, tp_price)
create_stop_order(sym, side, qty, sl_price)

# Step 10: 포지션 저장
with positions_lock:
    positions[sym] = {
        'side': primary_sig,
        'quantity': qty,
        'start_time': time.time(),
        'interval': '1m',
        'primary_tf': primary_tf,
        'sig1_count': sig1_count,
        'sig5_count': sig5_count,
        'aux_count': aux_count
    }

# Step 11: 텔레그램 전송
msg = (
    f"<b>🔹 ENTRY: {sym}</b>\n"
    f"▶ 방향: {primary_sig.upper()} (TF: {primary_tf})\n"
    f"▶ 근거: 1m={sig1_count}, 5m={sig5_count}, 보조={aux_count}\n"
    f"▶ TP: {tp_pct * 100:.2f}% | SL: {sl_pct * 100:.2f}%"
)
send_telegram(msg)

                    logging.info(
                        f"{sym} 진입 완료 → entry_price={entry_price:.4f}, TP={tp_price:.4f}, SL={sl_price:.4f}")

                    time.sleep(0.05)

                    with positions_lock:
                        if len(positions) >= MAX_POSITIONS:
                            logging.info("MAX_POSITIONS 도달, 분석 루프 탈출")
                            break

            time.sleep(ANALYSIS_INTERVAL_SEC)

        except Exception as e:
            logging.error(f"Error in analyze_market: {e}")
            time.sleep(ANALYSIS_INTERVAL_SEC)

def close_callback(symbol, side, pnl_pct, pnl_usdt):
    """
    포지션 청산 콜백. 터미널과 텔레그램에 한 줄 요약만 남깁니다.
    """
    global wins, losses
    timestamp = time.time()

    # (1) 승/패 카운트 업데이트
    if pnl_pct > 0:
        wins += 1
    else:
        losses += 1

    # (2) 터미널: 심볼, 방향(롱/숏), 수익금(USDT), 수익률(%)
    direction_kr = '롱' if side == 'long' else '숏'
    logging.info(
        f"{symbol} 청산 ({direction_kr}/{pnl_usdt:.2f}USDT,{pnl_pct * 100:.2f}%)"
    )

    # (3) 텔레그램: EXIT 메시지 + 전체 기록(wins,losses)
    msg = (
        f"<b>🔸 EXIT: {symbol}</b>\n"
        f"▶ 방향: {direction_kr}\n"
        f"▶ PnL: {pnl_pct * 100:.2f}% ({pnl_usdt:.2f} USDT)\n"
        f"▶ 전체 기록: {wins}승 {losses}패"
    )
    send_telegram(msg)


if __name__ == "__main__":
    positions = {}
    positions_lock = threading.Lock()

    trade_log = []
    trade_log_lock = threading.Lock()

    send_telegram("<b>🤖 자동매매 봇이 시작되었습니다!</b>")
    logging.info("자동매매 봇 시작 알림 전송 완료")

    start_summary_scheduler(trade_log, trade_log_lock)
    logging.info("Trade Summary 스케줄러 시작 완료")

    pos_monitor = PositionMonitor(positions, positions_lock, trade_log, trade_log_lock, close_callback)
    pos_monitor.start()
    logging.info("PositionMonitor 스레드 시작 완료")

    threading.Thread(target=analyze_market, daemon=True).start()
    logging.info("Analyze Market 스레드 시작 완료")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pos_monitor.stop()
        logging.info("Bot stopped by user.")
