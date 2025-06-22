"""Donchian 기반 Pullback 전략 모듈 (개선 버전)
 - 랜덤 진입 확률 낮춤 (보수적 조건)
 - RSI 또는 Volume 필터 반드시 통과해야 진입
 - 심볼별 30분 쿨타임 적용
"""

import datetime
import random

import utils


class StrategyPullback:
    """Donchian Pullback 전략 클래스"""

    name = "PULLBACK"

    def __init__(self):
        self.last_entry_time = {}  # {symbol: 마지막 진입 시각}

    def is_in_cooldown(self, symbol: str) -> bool:
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self):
        symbol = random.choice(["SOLUSDT", "MATICUSDT", "DOGEUSDT"])
        if self.is_in_cooldown(symbol):
            return None

        # 보수적 조건: breakout & pullback 모두 충족 + 필터 중 하나는 반드시 True
        breakout = random.random() < 0.25
        pullback = random.random() < 0.25
        rsi_filter = random.random() < 0.5
        volume_filter = random.random() < 0.5

        if breakout and pullback and (rsi_filter or volume_filter):
            side = random.choice(["LONG", "SHORT"])
            entry_price = round(random.uniform(10, 40), 2)
            self.last_entry_time[symbol] = datetime.datetime.utcnow()
            return {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
            }

        return None
