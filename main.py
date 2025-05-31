# main.py

import time
import threading
import logging
from decimal import Decimal
import operator

import pandas as pd

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
from strategy import check_entry_multi, calculate_ema_cross
from position_monitor import PositionMonitor
from trade_summary import start_summary_scheduler
from telegram_notifier import send_telegram
from utils import to_kst, calculate_qty

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

# ─────────────────────────────────────────────────────────────────────────────
# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ─────────────────────────────────────────────────────────────────────────────
# 진입 관련 상수
PRIMARY_THRESHOLD = 1          # 1분봉 또는 5분봉 지표 최소 개수
AUX_COUNT_THRESHOLD = 1        # 보조지표 최소 개수
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
                    logging.info(f"유효 심볼 리스트 갱신 → 24h 상위 100개 거래량 심볼 사용: 총 {len(tradable_symbols)}개")
                    logging.debug(f"Top5 샘플: {tradable_symbols[:5]}")
                else:
                    tradable_symbols = get_tradable_futures_symbols()
                    logging.warning("get_top_100_volume_symbols() 실패 → 전체 tradable 심볼 사용")

            now = to_kst(time.time())
            with positions_lock:
                current_positions = len(positions)
            logging.info(f"{now.strftime('%H:%M:%S')} 📊 분석중... (포지션 {current_positions}/{MAX_POSITIONS})")

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
                        logging.warning(f"{sym} 1분봉 데이터 부족/오류 → df1 is None or len<50")
                        continue
                    if df5 is None or len(df5) < 50:
                        logging.warning(f"{sym} 5분봉 데이터 부족/오류 → df5 is None or len<50")
                        continue

                    sig1 = check_entry_multi(df1, threshold=PRIMARY_THRESHOLD)
                    sig5 = check_entry_multi(df5, threshold=PRIMARY_THRESHOLD)
                    logging.info(f"{sym} → sig1(1m): {sig1}, sig5(5m): {sig5}")

                    primary_sig = None
                    primary_tf = None
                    if sig1 and not sig5:
                        primary_sig = sig1; primary_tf = '1m'
                    elif sig5 and not sig1:
                        primary_sig = sig5; primary_tf = '5m'
                    elif sig1 and sig5 and sig1 == sig5:
                        primary_sig = sig1; primary_tf = 'both'
                    else:
                        logging.debug(f"{sym} primary 신호 불충분 or 상반됨 → sig1={sig1}, sig5={sig5}")
                        continue

                    logging.info(f"{sym} primary 신호: {primary_sig} (TF={primary_tf})")

                    # 보조지표 OR
                    aux_signals = []

                    df30 = get_ohlcv(sym, '30m', limit=EMA_LONG_LEN + 2)
                    if df30 is None or len(df30) < EMA_LONG_LEN:
                        logging.warning(f"{sym} 30분봉 데이터 부족/오류 → df30 is None or len<{EMA_LONG_LEN}")
                    else:
                        calculate_ema_cross(df30, short_len=EMA_SHORT_LEN, long_len=EMA_LONG_LEN)
                        last_ema_short = df30[f"_ema{EMA_SHORT_LEN}"].iloc[-1]
                        last_ema_long = df30[f"_ema{EMA_LONG_LEN}"].iloc[-1]
                        if last_ema_short > last_ema_long:
                            aux_signals.append("long")
                        elif last_ema_short < last_ema_long:
                            aux_signals.append("short")
                        logging.debug(f"{sym} EMA30 신호: {'long' if last_ema_short>last_ema_long else 'short' if last_ema_short<last_ema_long else '없음'}")

                    obv_sig = compute_obv_signal(df1)
                    if obv_sig: aux_signals.append(obv_sig)
                    logging.debug(f"{sym} OBV 신호: {obv_sig}")

                    vol_sig = compute_volume_spike_signal(df1)
                    if vol_sig: aux_signals.append(vol_sig)
                    logging.debug(f"{sym} 거래량 스파이크 신호: {vol_sig}")

                    bb_sig = compute_bollinger_signal(df1)
                    if bb_sig: aux_signals.append(bb_sig)
                    logging.debug(f"{sym} 볼린저 밴드 신호: {bb_sig}")

                    match_count = sum(1 for s in aux_signals if s == primary_sig)
                    logging.info(f"{sym} aux_signals={aux_signals}, match_count={match_count}")

                    if match_count < AUX_COUNT_THRESHOLD:
                        logging.debug(f"{sym} 보조지표 충족 못 함 → match_count={match_count}/{AUX_COUNT_THRESHOLD}")
                        continue

                    logging.info(f"{sym} → 진입 조건 충족 (primary_sig={primary_sig}, aux match={match_count})")

                    balance = get_balance()
                    mark_price = get_mark_price(sym)
                    if mark_price is None:
                        logging.warning(f"{sym} 마크가격 조회 실패 → mark_price is None")
                        continue

                    price_precision, qty_precision, min_qty = get_precision(sym)
                    if price_precision is None or qty_precision is None or min_qty is None:
                        logging.warning(f"{sym} 정밀도 정보 부족 → price_precision/qty_precision/min_qty 중 None")
                        continue

                    last_row = df5.iloc[-1]
                    high = Decimal(str(last_row['high']))
                    low = Decimal(str(last_row['low']))
                    close = Decimal(str(last_row['close']))
                    atr_pct = (high - low) / close

                    tp_pct, sl_pct = compute_tp_sl(atr_pct)
                    qty = calculate_qty(balance, Decimal(str(mark_price)), LEVERAGE, Decimal("1"), qty_precision, min_qty)
                    logging.info(f"{sym} 잔고={balance:.2f}, 가격={mark_price:.4f}, qty={qty}, min_qty={min_qty}")
                    if qty == 0 or qty < Decimal(str(min_qty)):
                        logging.warning(f"{sym} 수량 계산 실패/최소 수량 미달 → qty={qty}, min_qty={min_qty}")
                        continue

                    side = "BUY" if primary_sig == "long" else "SELL"
                    entry_order = create_market_order(sym, side, qty)
                    if entry_order is None:
                        logging.warning(f"{sym} 시장가 주문 실패, 스킵")
                        continue

                    entry_price = Decimal(str(entry_order['fills'][0]['price']))
                    if primary_sig == "long":
                        tp_price = float((entry_price * (Decimal("1") + tp_pct)).quantize(Decimal(f"1e-{price_precision}")))
                        sl_price = float((entry_price * (Decimal("1") - sl_pct)).quantize(Decimal(f"1e-{price_precision}")))
                    else:
                        tp_price = float((entry_price * (Decimal("1") - tp_pct)).quantize(Decimal(f"1e-{price_precision}")))
                        sl_price = float((entry_price * (Decimal("1") + sl_pct)).quantize(Decimal(f"1e-{price_precision}")))

                    create_stop_order(sym, 'SELL' if primary_sig == 'long' else 'BUY', sl_price, qty)
                    create_take_profit(sym, 'SELL' if primary_sig == 'long' else 'BUY', tp_price, qty)

                    with positions_lock:
                        positions[sym] = {
                            'side': primary_sig,
                            'quantity': qty,
                            'start_time': time.time(),
                            'interval': '1m',
                            'primary_tf': primary_tf
                        }

                    msg = (
                        f"<b>🔹 ENTRY: {sym}</b>\n"
                        f"▶ TF: {primary_tf}\n"
                        f"▶ 방향: {primary_sig.upper()}\n"
                        f"▶ 진입가: {entry_price:.4f}\n"
                        f"▶ TP: {tp_pct * 100:.2f}% | SL: {sl_pct * 100:.2f}%"
                    )
                    send_telegram(msg)
                    logging.info(f"{sym} 진입 완료 → entry_price={entry_price:.4f}, TP={tp_price:.4f}, SL={sl_price:.4f}")

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
    포지션 청산 콜백. trade_summary 스케줄러가 이 로그를 활용합니다.
    """
    timestamp = time.time()
    entry = {
        'timestamp': timestamp,
        'symbol': symbol,
        'side': side,
        'pnl_pct': pnl_pct,
        'pnl_usdt': pnl_usdt,
    }
    with trade_log_lock:
        trade_log.append(entry)

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
