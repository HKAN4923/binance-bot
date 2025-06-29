import logging
from datetime import datetime, timedelta
from price_ws import get_price
from utils import get_candles

class StrategyNR7:
    def __init__(self, symbols):
        self.name = "NR7"
        self.symbols = symbols
        self.entries = {}

    def _is_valid_time(self):
        now = datetime.utcnow() + timedelta(hours=9)  # 한국 시간
        return 9 <= now.hour < 10 or 21 <= now.hour < 22

    def _can_enter_today(self, symbol):
        today = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
        entry_list = self.entries.get(symbol, [])
        return entry_list.count(today) < 3

    def _record_entry(self, symbol):
        today = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
        self.entries.setdefault(symbol, []).append(today)

    def check_entry(self, symbol):
        try:
            if not self._is_valid_time():
                logging.debug(f"[NR7] {symbol} → 시간 조건 미충족")
                return None

            if not self._can_enter_today(symbol):
                logging.debug(f"[NR7] {symbol} → 1일 최대 진입 횟수 초과")
                return None

            candles = get_candles(symbol, interval="15m", limit=10)
            if len(candles) < 7:
                logging.debug(f"[NR7] {symbol} → 캔들 부족")
                return None

            # NR7 탐지: 7개 중 가장 range(고-저)가 짧은 날
            ranges = [float(c[2]) - float(c[3]) for c in candles[-7:]]
            min_range = min(ranges)
            if ranges[-1] > min_range:
                logging.debug(f"[NR7] {symbol} → NR7 아님")
                return None

            current_price = get_price(symbol)
            if current_price is None:
                logging.debug(f"[NR7] {symbol} → 현재가 조회 실패")
                return None

            prev_candle = candles[-2]
            high = float(prev_candle[2])
            low = float(prev_candle[3])

            # ✅ 완화된 조건: 범위 0.5% → 0.8% 돌파 기준
            if current_price > high * 1.008:
                logging.info(f"[NR7] {symbol} → 상단 돌파 (long)")
                self._record_entry(symbol)
                return {"symbol": symbol, "side": "LONG"}
            elif current_price < low * 0.992:
                logging.info(f"[NR7] {symbol} → 하단 돌파 (short)")
                self._record_entry(symbol)
                return {"symbol": symbol, "side": "SHORT"}

            logging.debug(f"[NR7] {symbol} → 조건 미충족 (현재가: {current_price}, 범위: {low}-{high})")
            return None

        except Exception as e:
            logging.error(f"[NR7] {symbol} 진입 오류: {e}")
            return None

    def check_exit(self, symbol, entry_side):
        try:
            candles = get_candles(symbol, interval="1m", limit=10)
            if len(candles) < 2:
                return False

            last_close = float(candles[-1][4])
            prev_close = float(candles[-2][4])

            if entry_side == "LONG" and last_close < prev_close:
                return True
            if entry_side == "SHORT" and last_close > prev_close:
                return True
            return False

        except Exception as e:
            logging.error(f"[NR7] {symbol} 청산 오류: {e}")
            return False
