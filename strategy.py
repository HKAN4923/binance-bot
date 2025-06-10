# strategy.py
import pandas as pd
import numpy as np
from config import Config
from binance_client import get_klines


class BaseStrategy:
    def _fetch(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        klines = get_klines(symbol, interval, limit)
        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qa", "nt", "tb", "tq", "ignore"
        ]
        df = pd.DataFrame(klines, columns=cols)
        df[["open", "high", "low", "close", "volume"]] = \
            df[["open", "high", "low", "close", "volume"]].astype(float)
        return df


class ATRBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol: str):
        df = self._fetch(symbol, Config.BREAKOUT_TF, Config.ATR_PERIOD * 3)
        if len(df) <= Config.ATR_PERIOD:
            return None

        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(Config.ATR_PERIOD).mean()
        prev, last = df.iloc[-2], df.iloc[-1]
        bh = prev["high"] + Config.ENTRY_MULTIPLIER * atr.iloc[-2]
        bl = prev["low"] - Config.ENTRY_MULTIPLIER * atr.iloc[-2]

        if last["close"] > bh:
            entry = last["close"]
            sl = entry - (entry - bh) * Config.SL_RATIO
            tp = entry + (entry - sl) * Config.TP_RATIO
            return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}

        if last["close"] < bl:
            entry = last["close"]
            sl = entry + (bl - entry) * Config.SL_RATIO
            tp = entry - (sl - entry) * Config.TP_RATIO
            return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}

        return None


class PreviousDayBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol: str):
        df = self._fetch(symbol, "1h", 60)
        if len(df) < 26:
            return None

        df["date"] = pd.to_datetime(df["open_time"], unit="ms").dt.date
        prev_day = df["date"].iloc[-1] - pd.Timedelta(days=1)
        prev_df = df[df["date"] == prev_day]
        if prev_df.empty:
            return None

        ph, pl = prev_df["high"].max(), prev_df["low"].min()
        last = df.iloc[-1]
        vol_ma = df["volume"].iloc[-6:-1].mean()

        if last["close"] > ph * 1.002 and last["volume"] > vol_ma:
            entry = last["close"]
            sl = min(ph, entry * (1 - Config.SL_RATIO))
            risk = entry - sl
            tp = entry + 2 * risk
            return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}

        if last["close"] < pl * 0.998 and last["volume"] > vol_ma:
            entry = last["close"]
            sl = max(pl, entry * (1 + Config.SL_RATIO))
            risk = sl - entry
            tp = entry - 2 * risk
            return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}

        return None


class MovingAveragePullbackStrategy(BaseStrategy):
    def generate_signal(self, symbol: str):
        df = self._fetch(symbol, "1h", 100)
        if len(df) < 55:
            return None

        ema20 = df["close"].ewm(span=20).mean()
        ema50 = df["close"].ewm(span=50).mean()
        prev, last = df.iloc[-2], df.iloc[-1]

        # Bullish pullback
        if (
            prev["close"] < ema20.iloc[-2]
            and prev["close"] < ema50.iloc[-2]
            and last["close"] > ema20.iloc[-1] >= ema50.iloc[-1]
        ):
            low = df["low"].iloc[-5:-1].min()
            if low >= ema50.iloc[-2]:
                entry = last["close"]
                sl = min(low, entry * (1 - Config.SL_RATIO))
                tp = entry + 1.5 * (entry - sl)
                return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}

        # Bearish pullback
        if (
            prev["close"] > ema20.iloc[-2]
            and prev["close"] > ema50.iloc[-2]
            and last["close"] < ema20.iloc[-1] <= ema50.iloc[-1]
        ):
            high = df["high"].iloc[-5:-1].max()
            if high <= ema50.iloc[-2]:
                entry = last["close"]
                sl = max(high, entry * (1 + Config.SL_RATIO))
                tp = entry - 1.5 * (sl - entry)
                return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}

        return None


def check_entry_multi(df, threshold):
    if df is None or len(df) < 20:
        return None
    long_s, short_s = 0, 0
    c, v = df["close"], df["volume"]

    # MA
    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    long_s += ma5.iloc[-1] > ma20.iloc[-1]
    short_s += ma5.iloc[-1] < ma20.iloc[-1]

    # RSI
    delta = c.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    rsi = 100 - 100 / (1 + rs)
    long_s += rsi.iloc[-1] > 50
    short_s += rsi.iloc[-1] < 50

    # Bollinger
    sma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    long_s += c.iloc[-1] > sma20.iloc[-1] + 2 * std20.iloc[-1]
    short_s += c.iloc[-1] < sma20.iloc[-1] - 2 * std20.iloc[-1]

    # OBV
    obv = (np.sign(delta) * v).cumsum()
    long_s += obv.iloc[-1] > obv.iloc[-2]
    short_s += obv.iloc[-1] < obv.iloc[-2]

    # Volume spike
    long_s += v.iloc[-1] > v.rolling(20).mean().iloc[-1] * 2

    if max(long_s, short_s) < threshold:
        return None
    return "long" if long_s > short_s else "short"


def count_entry_signals(df):
    if df is None or len(df) < 20:
        return 0, 0
    l, s = 0, 0
    c, v = df["close"], df["volume"]

    # (동일 로직으로 집계)
    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    l += ma5.iloc[-1] > ma20.iloc[-1]; s += ma5.iloc[-1] < ma20.iloc[-1]

    delta = c.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    rsi = 100 - 100 / (1 + rs)
    l += rsi.iloc[-1] > 50; s += rsi.iloc[-1] < 50

    sma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    l += c.iloc[-1] > sma20.iloc[-1] + 2 * std20.iloc[-1]; s += c.iloc[-1] < sma20.iloc[-1] - 2 * std20.iloc[-1]

    obv = (np.sign(delta) * v).cumsum()
    l += obv.iloc[-1] > obv.iloc[-2]; s += obv.iloc[-1] < obv.iloc[-2]

    l += v.iloc[-1] > v.rolling(20).mean().iloc[-1] * 2
    return l, s
