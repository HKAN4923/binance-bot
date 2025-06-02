import pandas as pd
import logging
from config import EMA_SHORT_LEN, EMA_LONG_LEN
from utils import (
    calculate_rsi, calculate_macd, calculate_ema_cross,
    calculate_stochastic, calculate_adx, count_entry_signals,
    calculate_atr
)

def compute_all_signals(df: pd.DataFrame):
    """
    다중 지표를 계산해, 각 지표별 'long' 또는 'short' 반환.
    """
    try:
        # 1) 지표 계산
        calculate_rsi(df)
        calculate_macd(df)
        calculate_ema_cross(df, short_period=EMA_SHORT_LEN, long_period=EMA_LONG_LEN)
        calculate_stochastic(df)
        calculate_adx(df)

        signals = {}

        # RSI - 임계값 조정 (35->40, 65->60)
        last_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        if prev_rsi < 40 < last_rsi:     # 35 → 40
            signals['rsi'] = 'long'
        elif prev_rsi > 60 > last_rsi:   # 65 → 60
            signals['rsi'] = 'short'
        else:
            signals['rsi'] = None

        # MACD - 조건 변경 없음
        prev_hist = df['macd_hist'].iloc[-2]
        last_hist = df['macd_hist'].iloc[-1]
        if prev_hist < 0 < last_hist:
            signals['macd'] = 'long'
        elif prev_hist > 0 > last_hist:
            signals['macd'] = 'short'
        else:
            signals['macd'] = None

        # EMA Cross - 조건 변경 없음
        prev_ema_s = df['ema_short'].iloc[-2]
        prev_ema_l = df['ema_long'].iloc[-2]
        last_ema_s = df['ema_short'].iloc[-1]
        last_ema_l = df['ema_long'].iloc[-1]
        if prev_ema_s < prev_ema_l < last_ema_s:
            signals['ema'] = 'long'
        elif prev_ema_s > prev_ema_l > last_ema_s:
            signals['ema'] = 'short'
        else:
            signals['ema'] = None

        # Stochastic - 임계값 조정 (20->25, 80->75)
        prev_K = df['%K'].iloc[-2]
        prev_D = df['%D'].iloc[-2]
        last_K = df['%K'].iloc[-1]
        last_D = df['%D'].iloc[-1]
        if prev_K < 25 < last_K and last_K > last_D:   # 20 → 25
            signals['stoch'] = 'long'
        elif prev_K > 75 > last_K and last_K < last_D: # 80 → 75
            signals['stoch'] = 'short'
        else:
            signals['stoch'] = None

        # ADX - 임계값 상향 (20->25)
        last_adx = df['ADX'].iloc[-1]
        last_plus = df['+DI'].iloc[-1]
        last_minus = df['-DI'].iloc[-1]
        if last_adx > 25 and last_plus > last_minus:   # 20 → 25
            signals['adx'] = 'long'
        elif last_adx > 25 and last_minus > last_plus: # 20 → 25
            signals['adx'] = 'short'
        else:
            signals['adx'] = None

        return signals

    except Exception as e:
        logging.error(f"Error in compute_all_signals: {e}")
        return {}

def check_entry_multi(df: pd.DataFrame, threshold: int):
    """
    여러 지표(signal)에서 threshold 이상 일치하면 'long' 또는 'short' 반환.
    """
    try:
        long_count, short_count = count_entry_signals(df)
        if long_count >= threshold:
            return 'long'
        if short_count >= threshold:
            return 'short'
        return None
    except Exception as e:
        logging.error(f"진입 신호 확인 오류: {e}")
        return None

def check_reversal_multi(df: pd.DataFrame, threshold: int = 3):
    """
    다중 반전 신호를 체크하는 예시 함수.
    실제 전략에 맞춰 내부 로직을 수정하세요.
    - df: pandas DataFrame (1분봉 등)
    - threshold: 반전 신호 임계값 (기본 3)
    반환: 반전 신호 감지 시 True
    """
    try:
        signals = compute_all_signals(df)
        # 예시: long이 많다가 short 신호가 일정 이상 나오면 반전으로 간주
        long_count = sum(1 for v in signals.values() if v == 'long')
        short_count = sum(1 for v in signals.values() if v == 'short')
        # 만약 short_count가 threshold 이상이면 반전(매도) 신호로 본다
        if short_count >= threshold:
            return True
        # 반대로 주로 short였다가 long_count가 threshold 이상이면 반전(매수) 신호로 본다
        if long_count >= threshold and short_count == 0:
            return False  # 필요하면 True로 변경 가능
        return False
    except Exception as e:
        logging.error(f"check_reversal_multi 오류: {e}")
        return False
