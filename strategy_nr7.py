"""NR7 전략 모듈"""

import datetime
import random

import utils
from utils import to_kst


class StrategyNR7:
    """NR7 전략 클래스"""

    name = "NR7"

    def __init__(self):
        self.entered_blocks = set()  # (symbol:날짜:시간대)

    def get_active_block(self) -> tuple[str, str] | None:
        """현재가 속한 전략 실행 시간대(KOR/CHN/USA) 블록 반환"""
        now_kst = to_kst(datetime.datetime.utcnow())
        current = now_kst.time()
        date = now_kst.date().isoformat()

        blocks = {
            "KOR": (datetime.time(9, 0), datetime.time(10, 0)),
            "CHN": (datetime.time(10, 0), datetime.time(11, 0)),
            "USA": (datetime.time(21, 0), datetime.time(22, 0)),
        }

        for block_name, (start, end) in blocks.items():
            if start <= current <= end:
                return (date, block_name)

        return None

    def check_entry(self):
        """진입 조건 충족 시 시그널 반환"""

        block = self.get_active_block()
        if block is None:
            return None

        symbol = random.choice(["ETHUSDT", "BNBUSDT", "XRPUSDT"])
        block_id = f"{symbol}:{block[0]}:{block[1]}"
        if block_id in self.entered_blocks:
            return None

        if random.random() < 0.05:
            side = random.choice(["LONG", "SHORT"])
            entry_price = round(random.uniform(10, 50), 2)
            self.entered_blocks.add(block_id)
            return {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
            }

        return None
