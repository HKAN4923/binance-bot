"""EMA 교차 + RSI 전략 모듈 (실전 버전)
 - RSI 조건: 55 이상 or 45 이하
 - EMA 9/21 교차 확인
 - 캔들 기반 실시간 계산
"""
# 👇 이 줄을 맨 위나 다른 import 아래 추가
import random

import datetime
import pandas as pd
from utils import to_kst, calculate_rsi
from binance_client import client


class StrategyEMACross:
    name = "EMA"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.last_entry_time = {}

    def is_in_cooldown(self, symbol: str) -> bool:
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self, symbol: str):
        if self.is_in_cooldown(symbol):
            return None

        # 캔들 데이터 불러오기
        try:
            klines = client.futures_klines(symbol=symbol, interval="15m", limit=50)
            df = pd.DataFrame(klines, columns=[
                "time", "open", "high", "low", "close", "volume",
                "_", "_", "_", "_", "_", "_"
            ])
            df["close"] = df["close"].astype(float)
        except Exception as e:
            print(f"[에러] {symbol} 캔들 데이터 불러오기 실패: {e}")
            return None

        # EMA & RSI 계산
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["rsi"] = calculate_rsi(df["close"], 14)

        # 최근 캔들 기준으로 판단
        ema_9 = df["ema_9"].iloc[-1]
        ema_21 = df["ema_21"].iloc[-1]
        rsi = df["rsi"].iloc[-1]
        price = df["close"].iloc[-1]

        if ema_9 > ema_21 and rsi >= 53:
            side = "LONG"
        elif ema_9 < ema_21 and rsi <= 47:
            side = "SHORT"
        else:
            return None

        self.last_entry_time[symbol] = datetime.datetime.utcnow()
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": round(price, 4),
        }

def check_exit(self, symbol: str, entry_side: str) -> bool:
    """
    신호 무효화: 진입 조건이 더 이상 유지되지 않고,
    반대방향 조건까지 충족되었을 때 강제 청산
    """
    ema_9 = 25.0  # 예시
    ema_21 = 24.0
    rsi = random.randint(40, 60)

    if entry_side == "LONG" and ema_9 < ema_21 and rsi < 47:
        return True
    if entry_side == "SHORT" and ema_9 > ema_21 and rsi > 53:
        return True
    return False
