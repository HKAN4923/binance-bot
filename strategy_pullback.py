"""Donchian 기반 Pullback 전략 모듈 (라쉬케 변형 아님)
 - 고점/저점 돌파 후 Pullback 진입
 - RSI 또는 Volume 필터 통과 필수
 - 심볼별 30분 쿨타임 적용
"""

import datetime
import pandas as pd
from binance_client import client


class StrategyPullback:
    name = "PULLBACK"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.last_entry_time = {}  # {symbol: 마지막 진입 시각}

    def is_in_cooldown(self, symbol: str) -> bool:
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self, symbol: str):
        if self.is_in_cooldown(symbol):
            return None

        try:
            klines = client.futures_klines(symbol=symbol, interval="15m", limit=30)
            df = pd.DataFrame(klines, columns=[
                "time", "open", "high", "low", "close", "volume",
                "_", "_", "_", "_", "_", "_"
            ])
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["close"] = df["close"].astype(float)
            df["volume"] = df["volume"].astype(float)

            # Donchian High/Low 기준
            donchian_high = df["high"].iloc[:-3].max()
            donchian_low = df["low"].iloc[:-3].min()
            recent_close = df["close"].iloc[-1]
            recent_volume = df["volume"].iloc[-1]
            volume_ma = df["volume"].iloc[-6:-1].mean()

            # Pullback 조건
            breakout_up = df["close"].iloc[-4] > donchian_high
            breakout_down = df["close"].iloc[-4] < donchian_low
            pullback_ok = abs(df["close"].iloc[-1] - df["close"].iloc[-2]) < 0.01 * recent_close

            rsi = self._calculate_rsi(df["close"])
            rsi_filter = (rsi > 50) if breakout_up else (rsi < 50)
            volume_filter = recent_volume > volume_ma

            if breakout_up and pullback_ok and (rsi_filter or volume_filter):
                side = "LONG"
            elif breakout_down and pullback_ok and (rsi_filter or volume_filter):
                side = "SHORT"
            else:
                return None

            self.last_entry_time[symbol] = datetime.datetime.utcnow()
            return {
                "symbol": symbol,
                "side": side,
                "entry_price": round(recent_close, 4),
            }

        except Exception as e:
            print(f"[PULLBACK 오류] {symbol} 데이터 오류: {e}")
            return None

    def _calculate_rsi(self, close_series: pd.Series, period: int = 14) -> float:
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        return rsi_series.iloc[-1]
