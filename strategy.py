# strategy.py
import pandas as pd
import numpy as np
import logging
from decimal import Decimal
from config import EMA_SHORT_LEN, EMA_LONG_LEN

def calculate_rsi(df: pd.DataFrame, length: int = 9):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

def calculate_macd(df: pd.DataFrame, fast: int = 8, slow: int = 17, signal_len: int = 9):
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_len, adjust=False).mean()
    df['macd_hist'] = macd - signal

def calculate_ema(df: pd.DataFrame, span: int):
    return df['close'].ewm(span=span, adjust=False).mean()

def calculate_ema_cross(df: pd.DataFrame, short_len: int = EMA_SHORT_LEN, long_len: int = EMA_LONG_LEN):
    df['ema_short'] = calculate_ema(df, short_len)
    df['ema_long'] = calculate_ema(df, long_len)

def calculate_stochastic(df: pd.DataFrame, k_period: int = 9, d_period: int = 3):
    low_min = df['low'].rolling(k_period).min()
    high_max = df['high'].rolling(k_period).max()
    df['%K'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['%D'] = df['%K'].rolling(d_period).mean()

def calculate_adx(df: pd.DataFrame, length: int = 10):
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['+DM'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0.0)
    df['-DM'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0.0)
    df['TR'] = np.maximum.reduce([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ])
    atr = df['TR'].rolling(length).mean()
    df['+DI'] = (df['+DM'] / atr) * 100
    df['-DI'] = (df['-DM'] / atr) * 100
    df['DX'] = (df['+DI'] - df['-DI']).abs() / (df['+DI'] + df['-DI']) * 100
    df['ADX'] = df['DX'].rolling(length).mean()

def calculate_atr(df: pd.DataFrame, length: int = 14):
    df['TR'] = np.maximum.reduce([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()
    ])
    return df['TR'].rolling(length).mean()

def compute_all_signals(df: pd.DataFrame):
    """
    다중 지표를 계산해, 각 지표별 'long' 또는 'short' 반환.
    """
    try:
        calculate_rsi(df)
        calculate_macd(df)
        calculate_ema_cross(df)
        calculate_stochastic(df)
        calculate_adx(df)
        signals = {}

        # RSI
        last_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        if prev_rsi < 35 < last_rsi:
            signals['rsi'] = 'long'
        elif prev_rsi > 65 > last_rsi:
            signals['rsi'] = 'short'
        else:
            signals['rsi'] = None

        # MACD
        prev_hist = df['macd_hist'].iloc[-2]
        last_hist = df['macd_hist'].iloc[-1]
        if prev_hist < 0 < last_hist:
            signals['macd'] = 'long'
        elif prev_hist > 0 > last_hist:
            signals['macd'] = 'short'
        else:
            signals['macd'] = None

        # EMA Cross
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

        # Stochastic
        prev_K = df['%K'].iloc[-2]
        prev_D = df['%D'].iloc[-2]
        last_K = df['%K'].iloc[-1]
        last_D = df['%D'].iloc[-1]
        if prev_K < 20 < last_K and last_K > last_D:
            signals['stoch'] = 'long'
        elif prev_K > 80 > last_K and last_K < last_D:
            signals['stoch'] = 'short'
        else:
            signals['stoch'] = None

        # ADX
        last_adx = df['ADX'].iloc[-1]
        last_plus = df['+DI'].iloc[-1]
        last_minus = df['-DI'].iloc[-1]
        if last_adx > 20 and last_plus > last_minus:
            signals['adx'] = 'long'
        elif last_adx > 20 and last_minus > last_plus:
            signals['adx'] = 'short'
        else:
            signals['adx'] = None

        return signals
    except Exception as e:
        logging.error(f"Error in compute_all_signals: {e}")
        return {}

def count_entry_signals(df: pd.DataFrame):
    """
    5개 지표 결과를 집계해 long_count, short_count 반환
    """
    signals = compute_all_signals(df)
    if not signals:
        return 0, 0
    long_count = sum(1 for v in signals.values() if v == 'long')
    short_count = sum(1 for v in signals.values() if v == 'short')
    return long_count, short_count

def check_entry_multi(df: pd.DataFrame, threshold: int):
    """
    threshold 이상 지표 일치 시 'long' 또는 'short'
    """
    long_count, short_count = count_entry_signals(df)
    if long_count >= threshold:
        return 'long'
    if short_count >= threshold:
        return 'short'
    return None

def check_reversal_multi(df: pd.DataFrame, threshold: int):
    """
    진입 후 반전 감시용: compute_all_signals을 여러 지표로 확신도 합산 방식 구현 가능.
    간단히 threshold 만큼 반대 신호가 나오면 True 반환.
    """
    signals = compute_all_signals(df)
    if not signals:
        return False
    reverse_count = sum(1 for v in signals.values() if v is not None)
    return reverse_count >= threshold
