# strategy.py
import pandas as pd
from utils import calculate_atr
import logging

# 각 전략 함수

def five_and_dime(df, multiplier=0.5):
    ranges = df['high'] - df['low']
    if len(ranges) < 5:
        return None
    avg = ranges[-5:-2].mean()
    if all(r <= avg * multiplier for r in ranges[-3:]):
        return 'BUY' if df['close'].iloc[-1] > df['open'].iloc[-1] else 'SELL'
    return None


def turtle_soup(df, lookback=20):
    if len(df) < lookback + 1:
        return None
    high_max = df['high'][-(lookback+1):-1].max()
    low_min = df['low'][-(lookback+1):-1].min()
    last = df.iloc[-1]
    if last['high'] > high_max and last['close'] < high_max:
        return 'SELL'
    if last['low'] < low_min and last['close'] > low_min:
        return 'BUY'
    return None


def mini_squeeze(df, period=20, std_mul=2):
    if len(df) < period * 2:
        return None
    sma = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    upper = sma + std_mul * std
    lower = sma - std_mul * std
    bw = (upper - lower) / sma
    if bw.iloc[-2] < bw[-(period*2):-2].mean():
        last = df.iloc[-1]
        if last['close'] > upper.iloc[-2]:
            return 'BUY'
        if last['close'] < lower.iloc[-2]:
            return 'SELL'
    return None


def lbr_opening_range(df, or_minutes=5):
    if len(df) < or_minutes + 1:
        return None
    opening = df.iloc[:or_minutes]
    high_or = opening['high'].max()
    low_or = opening['low'].min()
    last = df.iloc[-1]
    if last['high'] > high_or:
        return 'BUY'
    if last['low'] < low_or:
        return 'SELL'
    return None


def pivot_candle(df):
    if len(df) < 2:
        return None
    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    rng = last['high'] - last['low']
    if body < rng * 0.3:
        upper_tail = last['high'] - max(last['close'], last['open'])
        lower_tail = min(last['close'], last['open']) - last['low']
        if lower_tail > body * 2:
            return 'BUY'
        if upper_tail > body * 2:
            return 'SELL'
    return None


def check_entry(df):
    for fn in [five_and_dime, turtle_soup, mini_squeeze, lbr_opening_range, pivot_candle]:
        try:
            sig = fn(df)
            if sig:
                logging.info(f"Strategy {fn.__name__} -> {sig}")
                return sig
        except Exception as e:
            logging.error(f"{fn.__name__} error: {e}")
    return None
