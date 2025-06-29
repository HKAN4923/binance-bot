import logging
from datetime import datetime, timedelta
from price_ws import get_price
from utils import get_candles

class StrategyORB:
    def __init__(self, symbols):
        self.name = "ORB"
        self.symbols = symbols
        self.entries = {}  # 심볼별 진입 기록 {"BTCUSDT": ["2025-06-29"]}

    def _is_valid_time(self):
        now = datetime.utcnow() + timedelta(hours=9)  # 한국시간 기준
        return now.hour == 9 or now.hour == 21

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
                logging.debug(f"[ORB] {symbol} → 시간 조건 미충족")
                return None

            if not self._can_enter_today(symbol):
                logging.debug(f"[ORB] {symbol} → 1일 최대 진입 횟수 초과")
                return None

            candles = get_candles(symbol, interval="1m", limit=60)
            if len(candles) < 60:
                logging.debug(f"[ORB] {symbol} → 캔들 부족")
                return None

            open_range = candles[0:5]  # 시작 5분간 시세 범위
            open_high = max(float(c[2]) for c in open_range)
            open_low = min(float(c[3]) for c in open_range)
            open_range_size = open_high - open_low

            if open_range_size == 0:
                logging.debug(f"[ORB] {symbol} → 시작 구간 변동폭 0")
                return None

            current_price = get_price(symbol)
            if current_price is None:
                logging.debug(f"[ORB] {symbol} → 현재가 조회 실패")
                return None

            # ✅ 완화된 조건: 오차 허용 범위 0.05 → 0.08 (8%)
            if current_price > open_high * 1.008:
                logging.info(f"[ORB] {symbol} → 상단 돌파 (long)")
                self._record_entry(symbol)
                return {"symbol": symbol, "side": "LONG"}
            elif current_price < open_low * 0.992:
                logging.info(f"[ORB] {symbol} → 하단 돌파 (short)")
                self._record_entry(symbol)
                return {"symbol": symbol, "side": "SHORT"}

            logging.debug(f"[ORB] {symbol} → 조건 미충족 (가격: {current_price:.4f}, 범위: {open_low:.4f}-{open_high:.4f})")
            return None

        except Exception as e:
            logging.error(f"[ORB] {symbol} → 진입 오류: {e}")
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
            logging.error(f"[ORB] {symbol} → 청산 판단 오류: {e}")
            return False