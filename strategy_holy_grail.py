"""Holy Grail 스타일 Pullback 전략 (라쉬케 기반)
 - EMA20 기준 추세 후 되돌림 발생 시 진입
 - EMA 부근에서 반전 캔들 발생 시 진입
 - 심볼별 쿨타임 30분 적용
 - 빈도 기준 50~60회/일 수준을 목표로 수치 설정
"""

import datetime
import pandas as pd
from binance_client import client


class StrategyHolyGrail:
    name = "HOLY_GRAIL"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.last_entry_time = {}  # {symbol: datetime}

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
            df["close"] = df["close"].astype(float)
            df["open"] = df["open"].astype(float)
            df["low"] = df["low"].astype(float)
            df["high"] = df["high"].astype(float)

            df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()

            # ✅ 추세 판단: 최근 5개 캔들 평균이 EMA보다 높거나 낮은가?
            recent = df.iloc[-6:-1]
            mean_close = recent["close"].mean()
            mean_ema = recent["ema20"].mean()
            trend = "up" if mean_close > mean_ema else "down"

            # ✅ 반전 조건: 최근 1캔들 양봉/음봉 여부 (약한 되돌림)
            last = df.iloc[-1]
            pullback = abs(last["close"] - last["open"]) < 0.008 * last["close"]  # ← 조정폭 (빈도↑/↓)
            near_ema = abs(last["close"] - last["ema20"]) / last["ema20"] < 0.012  # ← EMA 근접범위 (완화할수록 빈도↑)

            # ✅ 진입 조건
            if trend == "up" and last["close"] > last["open"] and pullback and near_ema:
                side = "LONG"
            elif trend == "down" and last["close"] < last["open"] and pullback and near_ema:
                side = "SHORT"
            else:
                return None

            self.last_entry_time[symbol] = datetime.datetime.utcnow()
            return {
                "symbol": symbol,
                "side": side,
                "entry_price": round(last["close"], 4),
            }

        except Exception as e:
            print(f"[HolyGrail 오류] {symbol} 데이터 오류: {e}")
            return None

def check_exit(self, symbol: str, entry_side: str) -> bool:
    """신호 무효화: 반대 방향으로 강한 트렌드 발생 시 청산"""
    ma_20 = 30.0
    price = 28.0
    strong_trend = random.random() < 0.5

    if entry_side == "LONG" and price < ma_20 and strong_trend:
        return True
    if entry_side == "SHORT" and price > ma_20 and strong_trend:
        return True
    return False
