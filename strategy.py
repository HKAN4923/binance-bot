# strategy.py
import pandas as pd
import numpy as np
import logging
from decimal import Decimal
from config import EMA_SHORT_LEN, EMA_LONG_LEN
from utils import calculate_adx, calculate_stochastic, calculate_rsi, calculate_macd, calculate_ema_cross, count_entry_signals


# 신호 계산 오류 처리 강화
def compute_all_signals(df: pd.DataFrame):
    try:
        # 기존 계산 로직
        calculate_rsi(df)
        calculate_macd(df)
        calculate_ema_cross(df)
        calculate_stochastic(df)
        calculate_adx(df)
        
        signals = {}
        # [기존 신호 계산 로직]
        return signals
    except Exception as e:
        logging.error(f"신호 계산 오류: {e}")
        return {}

# 진입 신호 확인 로직 안정화
def check_entry_multi(df: pd.DataFrame, threshold: int):
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
    


# ... [기존 지표 계산 함수 동일] ...

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

        # RSI - 임계값 조정 (35->40, 65->60)
        last_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        if prev_rsi < 40 < last_rsi:  # 35 → 40
            signals['rsi'] = 'long'
        elif prev_rsi > 60 > last_rsi:  # 65 → 60
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
        if prev_K < 25 < last_K and last_K > last_D:  # 20 → 25
            signals['stoch'] = 'long'
        elif prev_K > 75 > last_K and last_K < last_D:  # 80 → 75
            signals['stoch'] = 'short'
        else:
            signals['stoch'] = None

        # ADX - 임계값 상향 (20->25)
        last_adx = df['ADX'].iloc[-1]
        last_plus = df['+DI'].iloc[-1]
        last_minus = df['-DI'].iloc[-1]
        if last_adx > 25 and last_plus > last_minus:  # 20 → 25
            signals['adx'] = 'long'
        elif last_adx > 25 and last_minus > last_plus:  # 20 → 25
            signals['adx'] = 'short'
        else:
            signals['adx'] = None

        return signals
    except Exception as e:
        logging.error(f"Error in compute_all_signals: {e}")
        return {}
