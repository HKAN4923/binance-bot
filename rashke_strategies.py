import pandas as pd
import numpy as np
from datetime import datetime, timezone
from risk_config import Config


class BaseStrategy:
    def __init__(self, client):
        self.client = client

    def _fetch(self, symbol, interval, limit=100):
        klines = self.client.get_klines(symbol, interval, limit=limit)
        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "q",
            "n",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ]
        df = pd.DataFrame(klines, columns=columns)
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert(Config.TIMEZONE)
        return df


class ATRBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol):
        df = self._fetch(symbol, Config.BREAKOUT_TF, Config.ATR_PERIOD * 3)
        if len(df) <= Config.ATR_PERIOD:
            return None
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(Config.ATR_PERIOD).mean()
        prev = df.iloc[-2]
        last = df.iloc[-1]
        breakout_high = prev["high"] + Config.ENTRY_MULTIPLIER * atr.iloc[-2]
        breakout_low = prev["low"] - Config.ENTRY_MULTIPLIER * atr.iloc[-2]

        if last["close"] > breakout_high:
            entry = last["close"]
            sl = entry - (entry - breakout_high) * Config.SLTP_RATIO
            tp = entry + (entry - sl) * 1.8
            return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}
        elif last["close"] < breakout_low:
            entry = last["close"]
            sl = entry + (breakout_low - entry) * Config.SLTP_RATIO
            tp = entry - (sl - entry) * 1.8
            return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}
        return None


class PreviousDayBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol):
        df = self._fetch(symbol, "1h", 60)
        if len(df) < 26:
            return None
        df["date"] = df["open_time"].dt.date
        last_day = df["date"].iloc[-1]
        prev_day = last_day - pd.Timedelta(days=1)
        prev_df = df[df["date"] == prev_day]
        if prev_df.empty:
            return None
        prev_high = prev_df["high"].max()
        prev_low = prev_df["low"].min()
        last = df.iloc[-1]
        volume_ma = df["volume"].iloc[-6:-1].mean()
        if last["close"] > prev_high * 1.002 and last["volume"] > volume_ma:
            entry = last["close"]
            sl = min(prev_high, entry * 0.995)
            risk = entry - sl
            tp = entry + 2 * risk
            return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}
        if last["close"] < prev_low * 0.998 and last["volume"] > volume_ma:
            entry = last["close"]
            sl = max(prev_low, entry * 1.005)
            risk = sl - entry
            tp = entry - 2 * risk
            return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}
        return None


class MovingAveragePullbackStrategy(BaseStrategy):
    def generate_signal(self, symbol):
        df = self._fetch(symbol, "1h", 100)
        if len(df) < 55:
            return None
        ema20 = df["close"].ewm(span=20, adjust=False).mean()
        ema50 = df["close"].ewm(span=50, adjust=False).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # bullish setup
        if prev["close"] < ema20.iloc[-2] and prev["close"] < ema50.iloc[-2] and last["close"] > ema20.iloc[-1] >= ema50.iloc[-1]:
            pullback_low = df["low"].iloc[-5:-1].min()
            if pullback_low >= ema50.iloc[-2]:
                entry = last["close"]
                sl = min(pullback_low, entry * 0.992)
                risk = entry - sl
                tp = entry + 1.5 * risk
                return {"side": "BUY", "entry": entry, "sl": sl, "tp": tp}

        # bearish setup
        if prev["close"] > ema20.iloc[-2] and prev["close"] > ema50.iloc[-2] and last["close"] < ema20.iloc[-1] <= ema50.iloc[-1]:
            pullback_high = df["high"].iloc[-5:-1].max()
            if pullback_high <= ema50.iloc[-2]:
                entry = last["close"]
                sl = max(pullback_high, entry * 1.008)
                risk = sl - entry
                tp = entry - 1.5 * risk
                return {"side": "SELL", "entry": entry, "sl": sl, "tp": tp}
        return None
