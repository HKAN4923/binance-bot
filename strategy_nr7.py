"""NR7 전략 모듈 (라쉬케 기준 개선형)
 - 최근 7봉 중 가장 좁은 범위 대신, 평균 대비 좁은 봉으로 완화
 - 한국/중국/미국 장 시작 시간대에만 진입
 - 동일 심볼 하루 최대 3회 진입
 - 신호 반전 시 청산 (open > close 기준)
"""

import datetime
import pandas as pd
from utils import to_kst, get_candles

class StrategyNR7:
    name = "NR7"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.entry_counter = {}  # {symbol: {날짜: 진입횟수}}

    def get_active_block(self) -> bool:
        now_kst = to_kst(datetime.datetime.utcnow())
        current = now_kst.time()
        kor_block = datetime.time(9, 0) <= current <= datetime.time(10, 0)
        chn_block = datetime.time(10, 0) <= current <= datetime.time(11, 0)
        usa_block = datetime.time(21, 0) <= current <= datetime.time(22, 0)
        return kor_block or chn_block or usa_block

    def check_entry(self, symbol: str):
        if not self.get_active_block():
            return None

        now_kst = to_kst(datetime.datetime.utcnow())
        date_str = now_kst.date().isoformat()
        count = self.entry_counter.get(symbol, {}).get(date_str, 0)
        if count >= 3:
            return None

        try:
            candles = get_candles(symbol, interval="15m", limit=8)
            if len(candles) < 8:
                return None

            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]
            opens = [float(c[1]) for c in candles]
            closes = [float(c[4]) for c in candles]

            ranges = [h - l for h, l in zip(highs, lows)]
            avg_range = sum(ranges[:-1]) / len(ranges[:-1])
            curr_range = ranges[-1]

            if curr_range < avg_range * 0.75:
                side = "LONG" if closes[-1] > opens[-1] else "SHORT"
                price = closes[-1]

                self.entry_counter.setdefault(symbol, {}).setdefault(date_str, 0)
                self.entry_counter[symbol][date_str] += 1

                return {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": round(price, 4),
                }

        except Exception as e:
            print(f"[NR7 오류] {symbol} 데이터 오류: {e}")

        return None

    def check_exit(self, symbol: str, entry_side: str) -> bool:
        """신호 무효화 기준: 반대 방향 캔들 출현 (open > close)"""
        try:
            candles = get_candles(symbol, interval="15m", limit=2)
            if len(candles) < 2:
                return False

            open_price = float(candles[-1][1])
            close_price = float(candles[-1][4])

            if entry_side == "LONG" and close_price < open_price:
                return True
            if entry_side == "SHORT" and close_price > open_price:
                return True
            return False

        except Exception as e:
            print(f"[NR7 청산 오류] {symbol} 오류: {e}")
            return False
