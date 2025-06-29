import logging
from datetime import datetime
from price_ws import get_price
from utils import get_candles

# --------------------------------------
# ✅ ORB 전략 조건 설정 (라쉬케5 기준)
# 진입폭: 초기 고가/저가 기준 0.8% 돌파
# --------------------------------------
BREAKOUT_THRESHOLD = 0.008  # 0.8%

class StrategyORB:
    def __init__(self, symbols):
        self.name = "ORB"
        self.symbols = symbols
        self.open_ranges = {}

    def check_entry(self, symbol):
        try:
            now = datetime.utcnow()
            key = f"{symbol}_{now.date()}"

            if key not in self.open_ranges:
                candles = get_candles(symbol, interval="5m", limit=2)
                if len(candles) < 2:
                    logging.debug(f"[ORB] {symbol} → 초기 캔들 부족")
                    return None

                open_high = max(float(c[2]) for c in candles)
                open_low = min(float(c[3]) for c in candles)
                self.open_ranges[key] = (open_high, open_low)
                logging.debug(f"[ORB] {symbol} → 범위 저장: {open_high:.4f} / {open_low:.4f}")

            current_price = get_price(symbol)
            if current_price is None:
                logging.debug(f"[ORB] {symbol} → 현재가 없음")
                return None

            open_high, open_low = self.open_ranges[key]

            if current_price > open_high * (1 + BREAKOUT_THRESHOLD):
                logging.info(f"[ORB] {symbol} → 상단 돌파 (long)")
                return {"symbol": symbol, "side": "LONG"}
            elif current_price < open_low * (1 - BREAKOUT_THRESHOLD):
                logging.info(f"[ORB] {symbol} → 하단 돌파 (short)")
                return {"symbol": symbol, "side": "SHORT"}

            logging.debug(f"[ORB] {symbol} → 돌파 없음: price={current_price:.4f}, 기준: {open_high:.4f}/{open_low:.4f}")
            return None

        except Exception as e:
            logging.error(f"[ORB] {symbol} 진입 오류: {e}")
            return None

    def check_exit(self, symbol, entry_side):
        try:
            candles = get_candles(symbol, interval="5m", limit=2)
            if len(candles) < 2:
                return False

            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]

            if entry_side == "LONG" and lows[-1] < lows[-2]:
                return True
            if entry_side == "SHORT" and highs[-1] > highs[-2]:
                return True
            return False

        except Exception as e:
            logging.error(f"[ORB] {symbol} 청산 오류: {e}")
            return False
