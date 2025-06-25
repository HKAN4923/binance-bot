"""NR7 전략 모듈 (라쉬케 기준 적용)
 - 한국/중국/미국장 시작 시간대만 진입 (KST 기준)
 - 하루 동일 심볼 최대 3회 진입 허용
 - NR7 조건 충족 시 진입
"""

import datetime
import pandas as pd
from utils import to_kst
from binance_client import client


class StrategyNR7:
    name = "NR7"

    def __init__(self, symbol_list):
        self.symbol_list = symbol_list
        self.entry_counter = {}  # {symbol: {날짜: 진입횟수}}

    def get_active_block(self) -> bool:
        """현재 시각이 전략 허용 시간대인지 확인"""
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
            df = client.futures_klines(symbol=symbol, interval="15m", limit=8)
            df = pd.DataFrame(df, columns=[
                "time", "open", "high", "low", "close", "volume",
                "_", "_", "_", "_", "_", "_"
            ])
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["range"] = df["high"] - df["low"]

            # 최근 7개 중 마지막 봉이 가장 작은 range를 가졌는지 확인 (NR7)
            if df["range"].iloc[-1] < df["range"].iloc[:-1].min():
                side = "LONG" if df["close"].iloc[-1] > df["open"].iloc[-1] else "SHORT"
                price = float(df["close"].iloc[-1])

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
