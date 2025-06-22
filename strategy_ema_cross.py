"""EMA 교차 + RSI 필터 전략 모듈"""

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
        """재진입 제한 확인 (기본 30분)"""
        now = datetime.datetime.utcnow()
        last = self.last_entry_time.get(symbol)
        if last is None:
            return False
        return (now - last).total_seconds() < 1800  # 30분

    def check_entry(self):
        """진입 조건 충족 시 시그널 반환"""

        symbol = random.choice(["BNBUSDT", "AVAXUSDT", "LINKUSDT"])
        if self.is_in_cooldown(symbol):
            return None

        # 실제 환경에서는 캔들 불러와서 EMA/RSI 계산 필요
        ema_9 = 25.0
        ema_21 = 24.0
        rsi = random.randint(45, 65)

        # 조건: 골든크로스 + RSI > 50 → 롱
        # 조건: 데드크로스 + RSI < 50 → 숏
        if ema_9 > ema_21 and rsi > 50:
            side = "LONG"
        elif ema_9 < ema_21 and rsi < 50:
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
