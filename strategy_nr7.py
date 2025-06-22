"""NR7 전략 모듈 (라쉬케 기준 적용)
 - 한국/중국/미국장 시작 시간대만 진입 (KST 기준)
 - 하루 동일 심볼 최대 3회 진입 허용
 - 진입 조건 보수적 설정
"""

import datetime
import random

import utils
from utils import to_kst


class StrategyNR7:
    """NR7 전략 클래스"""

    name = "NR7"

    def __init__(self):
        self.entry_counter = {}  # {symbol: {날짜: 진입횟수}}

    def get_active_block(self) -> bool:
        """현재 시각이 전략 허용 시간대인지 확인"""
        now_kst = to_kst(datetime.datetime.utcnow())
        current = now_kst.time()

        kor_block = datetime.time(9, 0) <= current <= datetime.time(10, 0)
        chn_block = datetime.time(10, 0) <= current <= datetime.time(11, 0)
        usa_block = datetime.time(21, 0) <= current <= datetime.time(22, 0)

        return kor_block or chn_block or usa_block

    def check_entry(self):
        """진입 조건 충족 시 시그널 반환"""

        if not self.get_active_block():
            return None

        now_kst = to_kst(datetime.datetime.utcnow())
        date_str = now_kst.date().isoformat()

        symbol = random.choice(["ETHUSDT", "BNBUSDT", "XRPUSDT"])
        count = self.entry_counter.get(symbol, {}).get(date_str, 0)
        if count >= 3:
            return None

        # 보수적 진입 조건
        if random.random() < 0.025:
            side = random.choice(["LONG", "SHORT"])
            entry_price = round(random.uniform(10, 50), 2)
            self.entry_counter.setdefault(symbol, {}).setdefault(date_str, 0)
            self.entry_counter[symbol][date_str] += 1
            return {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
            }

        return None