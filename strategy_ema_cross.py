"""EMA 교차 + RSI 전략 모듈 (개선 버전)
 - RSI 조건 강화: 55 이상/45 이하만 진입
 - EMA 9/21 교차 조건
 - 심볼별 30분 쿨타임 적용
"""

import datetime
import random

import utils
from utils import to_kst, calculate_rsi


class StrategyEMACross:
    """EMA + RSI 전략 클래스"""

    name = "EMA"

    def __init__(self):
        self.last_entry_time = {}  # {symbol: 시각}

    def is_in_cooldown(self, symbol: str) -> bool:
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self):
        symbol = random.choice(["BNBUSDT", "AVAXUSDT", "LINKUSDT"])
        if self.is_in_cooldown(symbol):
            return None

        # 실제 환경에서는 캔들 데이터 불러와 EMA 계산 필요
        ema_9 = 25.0
        ema_21 = 24.0
        rsi = random.randint(40, 60)

        if ema_9 > ema_21 and rsi >= 55:
            side = "LONG"
        elif ema_9 < ema_21 and rsi <= 45:
            side = "SHORT"
        else:
            return None

        entry_price = round(random.uniform(10, 50), 2)
        self.last_entry_time[symbol] = datetime.datetime.utcnow()
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
        }
