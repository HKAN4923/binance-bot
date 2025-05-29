# utils/indicators.py

import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"]       = RSIIndicator(df["c"], 14).rsi()
    df["macd_diff"] = MACD(df["c"]).macd_diff()
    df["ema_short"] = EMAIndicator(df["c"], 9).ema_indicator()
    df["ema_long"]  = EMAIndicator(df["c"], 21).ema_indicator()
    df["adx"]       = ADXIndicator(df["h"], df["l"], df["c"], 14).adx()
    df["stoch"]     = StochasticOscillator(df["h"], df["l"], df["c"], 14).stoch()
    df["atr"]       = AverageTrueRange(df["h"], df["l"], df["c"], 14).average_true_range()
    return df.dropna()
