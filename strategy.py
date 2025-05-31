import pandas as pd
import numpy as np
import logging

def calculate_rsi(df: pd.DataFrame, length: int = 9):
    """
    RSI 계산 (length 기간).
    df['close'] 컬럼이 반드시 있어야 합니다.
    결과는 df['rsi'] 로 저장됩니다.
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi

def calculate_macd(df: pd.DataFrame, fast: int = 8, slow: int = 17, signal_len: int = 9):
    """
    MACD (fast=8, slow=17, signal=9).
    df['close'] 컬럼이 반드시 있어야 합니다.
    결과는 df['macd_hist'] 로 저장됩니다.
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_len, adjust=False).mean()
    hist = macd - signal
    df['macd_hist'] = hist

def calculate_ema_cross(df: pd.DataFrame, short_len: int = 9, long_len: int = 21):
    """
    EMA 9/21 교차 계산.
    df['close'] 컬럼이 반드시 있어야 합니다.
    결과는 df['_ema20'] 와 df['_ema50'] 로 저장됩니다.
    """
    df['_ema20'] = df['close'].ewm(span=short_len, adjust=False).mean()
    df['_ema50'] = df['close'].ewm(span=long_len, adjust=False).mean()

def calculate_stochastic(df: pd.DataFrame, k_period: int = 9, d_period: int = 3):
    """
    Stochastic %K/%D 계산 (k_period, d_period).
    df['high'], df['low'], df['close'] 컬럼이 반드시 있어야 합니다.
    결과는 df['%K'], df['%D'] 로 저장됩니다.
    """
    low_min = df['low'].rolling(k_period).min()
    high_max = df['high'].rolling(k_period).max()
    df['%K'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['%D'] = df['%K'].rolling(d_period).mean()

def calculate_adx(df: pd.DataFrame, length: int = 10):
    """
    ADX (10), +DI, -DI 계산.
    df['high'], df['low'], df['close'] 컬럼이 반드시 있어야 합니다.
    결과는 df['+DI'], df['-DI'], df['ADX'] 로 저장됩니다.
    """
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

def check_entry(df: pd.DataFrame):
    """
    기본 하나의 RSI 크로스(35/65) 진입 함수(호환용). 
    호환성 문제로 내부에서 그대로 두었습니다.
    """
    try:
        calculate_rsi(df)
        last_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        if prev_rsi < 35 and last_rsi > 35:
            return "long"
        if prev_rsi > 65 and last_rsi < 65:
            return "short"
        return None
    except Exception as e:
        logging.error(f"Error in check_entry: {e}")
        return None

def check_entry_multi(df: pd.DataFrame, threshold: int = 2):
    """
    5개 지표(RSI, MACD 히스토그램, EMA 20/50, Stochastic, ADX) 모두 계산한 뒤,
    'long' 혹은 'short' 신호가 나온 지표가 threshold(기본 3) 이상이면 방향 반환,
    그렇지 않으면 None.
    """
    try:
        # 1) RSI
        calculate_rsi(df)
        last_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        rsi_signal = None
        if prev_rsi < 35 and last_rsi > 35:
            rsi_signal = "long"
        elif prev_rsi > 65 and last_rsi < 65:
            rsi_signal = "short"

        # 2) MACD 히스토그램
        calculate_macd(df)
        prev_hist = df['macd_hist'].iloc[-2]
        last_hist = df['macd_hist'].iloc[-1]
        macd_signal = None
        if prev_hist < 0 and last_hist > 0:
            macd_signal = "long"
        elif prev_hist > 0 and last_hist < 0:
            macd_signal = "short"

        # 3) EMA20/50 크로스
        calculate_ema_cross(df)
        prev_ema20 = df['_ema20'].iloc[-2]
        prev_ema50 = df['_ema50'].iloc[-2]
        last_ema20 = df['_ema20'].iloc[-1]
        last_ema50 = df['_ema50'].iloc[-1]
        ema_signal = None
        if prev_ema20 < prev_ema50 and last_ema20 > last_ema50:
            ema_signal = "long"
        elif prev_ema20 > prev_ema50 and last_ema20 < last_ema50:
            ema_signal = "short"

        # 4) Stochastic
        calculate_stochastic(df)
        prev_K = df['%K'].iloc[-2]
        prev_D = df['%D'].iloc[-2]
        last_K = df['%K'].iloc[-1]
        last_D = df['%D'].iloc[-1]
        stoch_signal = None
        if prev_K < 20 and last_K > 20 and last_K > last_D:
            stoch_signal = "long"
        elif prev_K > 80 and last_K < 80 and last_K < last_D:
            stoch_signal = "short"

        # 5) ADX + DI
        calculate_adx(df)
        last_adx = df['ADX'].iloc[-1]
        last_plus = df['+DI'].iloc[-1]
        last_minus = df['-DI'].iloc[-1]
        adx_signal = None
        if last_adx > 20 and last_plus > last_minus:
            adx_signal = "long"
        elif last_adx > 20 and last_minus > last_plus:
            adx_signal = "short"

        # 개별 신호 카운트
        signals = [rsi_signal, macd_signal, ema_signal, stoch_signal, adx_signal]
        long_count = sum(1 for s in signals if s == "long")
        short_count = sum(1 for s in signals if s == "short")

        if long_count >= threshold:
            return "long"
        if short_count >= threshold:
            return "short"
        return None

    except Exception as e:
        logging.error(f"Error in check_entry_multi: {e}")
        return None

def check_entry_with_confidence(df: pd.DataFrame):
    """
    기존 1개 지표(RSI) 기반 confidence 반환용 함수(호환 유지).
    """
    try:
        sig = check_entry(df)
        if not sig:
            return {}
        rsi = df['rsi'].iloc[-1]
        if sig == 'long':
            conf = min((rsi - 35) / (100 - 35), 1)
        else:
            conf = min((65 - rsi) / 65, 1)
        return {"side": sig, "confidence": float(conf)}
    except Exception as e:
        logging.error(f"Error in check_entry_with_confidence: {e}")
        return {}
