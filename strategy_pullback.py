"""Donchian 기반 Pullback 전략 모듈"""

import datetime
import random

import utils


class StrategyPullback:
    """Donchian Pullback 전략 클래스"""

    name = "PULLBACK"

    def __init__(self):
        self.last_entry_time = {}  # {symbol: 마지막 진입 시각}

    def is_in_cooldown(self, symbol: str) -> bool:
        """30분 재진입 제한"""
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self):
        """진입 조건 확인"""

        symbol = random.choice(["SOLUSDT", "MATICUSDT", "DOGEUSDT"])
        if self.is_in_cooldown(symbol):
            return None

        # 시뮬레이션 로직: Donchian 돌파 후 되돌림 + 필터 통과 시 진입
        breakout = random.random() < 0.3
        pullback = random.random() < 0.3
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
