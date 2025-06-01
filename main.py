# main.py

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
from utils import to_kst, calculate_qty, get_top_100_volume_symbols, get_tradable_futures_symbols
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
    create_stop_order,
    create_take_profit,
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
PRIMARY_THRESHOLD = 3       # 1m/5m 지표 최소 일치 개수
AUX_COUNT_THRESHOLD = 2     # 보조지표 최소 일치 개수
EMA_SHORT_LEN = 20          # 30m EMA 단기
EMA_LONG_LEN = 50           # 30m EMA 장기
VOLUME_SPIKE_MULTIPLIER = 2  # 거래량 스파이크 임계값

# TP/SL 고정 비율 (1.75% / 1%)
TP_RATIO = Decimal("0.0175")
SL_RATIO = Decimal("0.01")

# ─────────────────────────────────────────────────────────────────────────────

# 메모리 상 포지션 기록
# 각 심볼별로 다음 정보를 저장:
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
    5개 지표(RSI, MACD 히스토그램, EMA20/50, Stochastic, ADX) 중
    long/short 신호 개수 반환
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


def monitor_position(sym):
    """
    진입 후 10초 간격으로 지표를 재확인하여 단계별 익절/청산 처리.
    1초마다 긴급 탈출 조건은 PositionMonitor가 담당.
    """
    with positions_lock:
        pos_info = positions.get(sym)
    if not pos_info:
        return

    side = pos_info['side']
    entry_price = pos_info['entry_price']
    initial_count = pos_info['initial_match_count']
    primary_sig = pos_info['primary_sig']

    while True:
        time.sleep(10)  # 10초마다 확인
        # 이미 포지션이 닫혔으면 종료
        amt = get_open_position_amt(sym)
        if amt == 0:
            break

        # 최신 1m/5m/30m 데이터로 지표 재계산
        df1 = get_ohlcv(sym, '1m', limit=50)
        time.sleep(0.1)
        df5 = get_ohlcv(sym, '5m', limit=50)
        time.sleep(0.1)
        if df1 is None or df5 is None:
            continue

        # primary_sig와 동일한 방향의 신호 개수 재계산
        sig1_long, sig1_short = count_entry_signals(df1)
        sig5_long, sig5_short = count_entry_signals(df5)
        current_count = max(sig1_long, sig1_short) + max(sig5_long, sig5_short)

        # 단계별 익절/청산 로직
        # 1) 신호 그대로 유지 → 아무 조치 없음
        if current_count == initial_count:
            continue

        # 2) 신호가 1만큼 줄었으면 50% 익절
        if current_count == initial_count - 1:
            take_qty = pos_info['quantity'] * Decimal("0.5")
            try:
                create_market_order(sym, "SELL" if side == "BUY" else "BUY", take_qty, reduceOnly=True)
                logging.info(f"{sym} 50% 익절 주문: {take_qty}")
            except Exception as e:
                logging.error(f"{sym} 50% 익절 실패: {e}")
            continue

        # 3) 신호가 2 이상 줄었으면 90% 익절
        if current_count <= initial_count - 2:
            take_qty = pos_info['quantity'] * Decimal("0.9")
            try:
                create_market_order(sym, "SELL" if side == "BUY" else "BUY", take_qty, reduceOnly=True)
                logging.info(f"{sym} 90% 익절 주문: {take_qty}")
            except Exception as e:
                logging.error(f"{sym} 90% 익절 실패: {e}")
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
            try:
                create_market_order(sym, "SELL" if side == "BUY" else "BUY", amt, reduceOnly=True)
                logging.info(f"{sym} 신호 반전 전량 청산 주문: {amt}")
            except Exception as e:
                logging.error(f"{sym} 신호 반전 청산 실패: {e}")
            break  # 모니터 종료

        # 나머지는 유지, 다음 10초 대기


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
                if tradable_symbols:
                    logging.info(
                        f"유효 심볼 리스트 갱신 → 24h 상위 100개 거래량 심볼 사용: 총 {len(tradable_symbols)}개"
                    )
                    logging.debug(f"Top5 샘플: {tradable_symbols[:5]}")
                else:
                    tradable_symbols = get_tradable_futures_symbols()
                    logging.warning("get_top_100_volume_symbols() 실패 → 전체 tradable 심볼 사용")

            while True:
                # 실시간으로 바이낸스에서 포지션 개수 조회
                current_positions = count_open_positions()
                now = to_kst(time.time())
                logging.info(
                    f"{now.strftime('%H:%M:%S')} 📊 분석중. (실제 포지션 {current_positions}/{MAX_POSITIONS})"
                )

                # 최대 포지션 수 초과 방지
                if current_positions >= MAX_POSITIONS:
                    break

                for sym in tradable_symbols:
                    # 진입 전 항상 real-time 포지션 개수 확인
                    if count_open_positions() >= MAX_POSITIONS:
                        break

                    # 메모리 상으로는 이미 기록된 심볼 건너뛰기
                    with positions_lock:
                        if sym in positions:
                            continue

                    # 1m, 5m 캔들 데이터 조회
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
                        logging.debug(f"{sym} primary 신호 불충분/상반됨 → sig1={sig1}, sig5={sig5}")
                        continue

                    # 보조지표 OR 로직
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

                    try:
                        # Step 1: 진입 수량 계산 정보 수집
                        balance = get_balance()
                        mark_price = get_mark_price(sym)

                        # Step 2: get_precision 예외 처리 추가
                        try:
                            price_precision, qty_precision, min_qty = get_precision(sym)
                        except Exception as e:
                            logging.error(f"{sym} get_precision 실패: {e}")
                            continue

                        # Step 3: 지표 개수 계산 시 예외 처리 추가
                        try:
                            sig1_long, sig1_short = count_entry_signals(df1)
                            sig5_long, sig5_short = count_entry_signals(df5)
                        except Exception as e:
                            logging.error(f"{sym} count_entry_signals 실패: {e}")
                            continue

                        initial_count = max(sig1_long, sig1_short) + max(sig5_long, sig5_short)

                        # Step 4: 진입 방향 설정
                        side = "BUY" if primary_sig == "long" else "SELL"
                        direction_kr = "롱" if primary_sig == "long" else "숏"

                        # Step 5: 진입 수량 계산 (자금의 30% 사용)
                        qty = calculate_qty(
                            balance,
                            Decimal(str(mark_price)),
                            LEVERAGE,
                            Decimal("0.3"),
                            qty_precision,
                            min_qty
                        )
                        if qty == 0 or qty < Decimal(str(min_qty)):
                            logging.warning(f"{sym} 수량 계산 실패/최소 수량 미달 → qty={qty}, min_qty={min_qty}")
                            continue

                        # Step 6: 시장가 주문
                        entry_order = create_market_order(sym, side, float(qty))
                        if entry_order is None:
                            logging.warning(f"{sym} 진입 실패 → 주문 실패 또는 증거금 부족")
                            continue

                        # Step 7: 진입가 추정
                        def get_entry_price(order, fallback_price):
                            try:
                                if 'fills' in order and order['fills']:
                                    return Decimal(str(order['fills'][0]['price']))
                                elif 'avgFillPrice' in order:
                                    return Decimal(str(order['avgFillPrice']))
                                else:
                                    return Decimal(str(fallback_price))
                            except Exception:
                                return Decimal(str(fallback_price))

                        entry_price = get_entry_price(entry_order, mark_price)

                        # Step 8: TP/SL 주문 생성
                        # TP/SL 가격 계산 및 소수점 처리
                        quant_price = Decimal('1e-{}'.format(price_precision))
                        if primary_sig == "long":
                            tp_price = (entry_price * (Decimal("1") + TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                            sl_price = (entry_price * (Decimal("1") - SL_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                            tp_order = create_take_profit(sym, "SELL", float(tp_price), float(qty))
                            sl_order = create_stop_order(sym, "SELL", float(sl_price), float(qty))
                        else:
                            tp_price = (entry_price * (Decimal("1") - TP_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                            sl_price = (entry_price * (Decimal("1") + SL_RATIO)).quantize(quant_price, rounding=ROUND_DOWN)
                            tp_order = create_take_profit(sym, "BUY", float(tp_price), float(qty))
                            sl_order = create_stop_order(sym, "BUY", float(sl_price), float(qty))

                        tp_id = tp_order.get('orderId') if tp_order else None
                        sl_id = sl_order.get('orderId') if sl_order else None

                        # Step 9: 포지션 메모리 저장
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

                        # Step 10: 진입 로그 및 텔레그램 전송
                        logging.info(f"{sym} ({direction_kr}/{initial_count}) 진입 완료 → entry_price={entry_price:.4f}, TP={tp_price}, SL={sl_price}")
                        try:
                            msg = (
                                f"<b>🔹 ENTRY: {sym}</b>\n"
                                f"▶ 방향: {primary_sig.upper()} (TF: {primary_tf})\n"
                                f"▶ 초기 신호 개수: {initial_count}\n"
                                f"▶ 진입가: {entry_price:.4f}\n"
                                f"▶ TP: {tp_price}\n"
                                f"▶ SL: {sl_price}"
                            )
                            send_telegram(msg)
                        except Exception as e:
                            logging.error(f"{sym} ENTRY 텔레그램 전송 오류: {e}")

                        # Step 11: 진입 후 10초마다 신호 감시 스레드 시작
                        threading.Thread(target=monitor_position, args=(sym,), daemon=True).start()

                    except Exception as e:
                        logging.error(f"{sym} 진입 블럭에서 오류 발생: {e}")
                        continue

                    # 포지션 개수가 제한치에 도달하면 루프 탈출
                    time.sleep(0.05)
                    if count_open_positions() >= MAX_POSITIONS:
                        logging.info("MAX_POSITIONS 도달, 분석 심볼 루프 탈출")
                        break

                break  # 한 번 분석 후 INTERVAL 기다리도록 루프 탈출

            time.sleep(ANALYSIS_INTERVAL_SEC)

        except Exception as e:
            logging.error(f"Error in analyze_market: {e}")
            time.sleep(ANALYSIS_INTERVAL_SEC)


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

    try:
        msg = (
            f"<b>🔸 EXIT: {symbol}</b>\n"
            f"▶ 방향: {direction_kr}\n"
            f"▶ PnL: {pnl_pct * 100:.2f}% ({pnl_usdt:.2f} USDT)\n"
            f"▶ 전체 기록: {wins}승 {losses}패"
        )
        send_telegram(msg)
    except Exception as e:
        logging.error(f"{symbol} EXIT 텔레그램 전송 오류: {e}")


if __name__ == "__main__":
    # 봇 시작 알림
    try:
        send_telegram("<b>🤖 자동매매 봇이 시작되었습니다!</b>")
    except Exception as e:
        logging.error(f"봇 시작 텔레그램 전송 오류: {e}")
    logging.info("자동매매 봇 시작 알림 전송 완료")

    # Trade Summary 스케줄러
    start_summary_scheduler(trade_log, trade_log_lock)
    logging.info("Trade Summary 스케줄러 시작 완료")

    # PositionMonitor 스레드 시작 (1초마다 긴급 탈출 체크)
    pos_monitor = PositionMonitor(positions, positions_lock, trade_log, trade_log_lock, close_callback)
    pos_monitor.start()
    logging.info("PositionMonitor 스레드 시작 완료")

    # Analyze Market 스레드 시작
    threading.Thread(target=analyze_market, daemon=True).start()
    logging.info("Analyze Market 스레드 시작 완료")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pos_monitor.stop()
        logging.info("Bot stopped by user.")
