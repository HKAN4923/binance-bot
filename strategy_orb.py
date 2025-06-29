"""Opening Range Breakout (ORB) 전략 모듈 (라쉬케 기준 적용)
 - 한국/미국장 시작 시간대만 진입 (KST 기준)
 - 하루 동일 심볼 최대 3회 진입 허용
 - 보수적 진입 조건
"""

import datetime
import pandas as pd
from utils import to_kst
from binance_client import client


class StrategyORB:
    name = "ORB"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.entry_counter = {}  # {symbol: {날짜: 진입횟수}}

    def get_active_block(self) -> bool:
        """현재 시각이 전략 허용 시간대인지 확인"""
        now_kst = to_kst(datetime.datetime.utcnow())
        current = now_kst.time()

        kor_block = datetime.time(9, 0) <= current <= datetime.time(10, 0)
        usa_block = datetime.time(21, 0) <= current <= datetime.time(22, 0)

        return kor_block or usa_block

    def check_entry(self, symbol: str):
        if not self.get_active_block():
            return None

        now_kst = to_kst(datetime.datetime.utcnow())
        date_str = now_kst.date().isoformat()
        count = self.entry_counter.get(symbol, {}).get(date_str, 0)
        if count >= 3:
            return None

        try:
            df = client.futures_klines(symbol=symbol, interval="1m", limit=20)
            df = pd.DataFrame(df, columns=[
                "time", "open", "high", "low", "close", "volume",
                "_", "_", "_", "_", "_", "_"
            ])
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["close"] = df["close"].astype(float)

            opening_range = df.iloc[0:5]
            rest = df.iloc[5:]

            high = opening_range["high"].max()
            low = opening_range["low"].min()
            last = rest.iloc[-1]

            if last["close"] > high * 1.0015:
                entry = last["close"]
                side = "LONG"
            elif last["close"] < low * 0.9985:
                entry = last["close"]
                side = "SHORT"
            else:
                return None

            # 진입 기록
            self.entry_counter.setdefault(symbol, {}).setdefault(date_str, 0)
            self.entry_counter[symbol][date_str] += 1

            return {
                "symbol": symbol,
                "side": side,
                "entry_price": round(entry, 4),
            }

        except Exception as e:
            print(f"[ORB 오류] {symbol} 데이터 오류: {e}")
            return None

def check_exit(self, symbol: str, entry_side: str) -> bool:
    """
    신호 무효화: 진입방향 반대 시초가 범위 돌파 시 청산
    (예: LONG인데 시초가 하단 돌파 → 무효화)
    """
    open_range_high = 25.0
    open_range_low = 24.0
    current_price = 23.5  # 예시

    if entry_side == "LONG" and current_price < open_range_low:
        return True
    if entry_side == "SHORT" and current_price > open_range_high:
        return True
    return False