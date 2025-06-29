import logging
from datetime import datetime, timedelta
from price_ws import get_price
from utils import get_candles, calculate_ema

class StrategyHolyGrail:
    def __init__(self, symbols):
        self.name = "HOLY_GRAIL"
        self.symbols = symbols

    def check_entry(self, symbol):
        try:
            candles = get_candles(symbol, interval="5m", limit=50)
            if len(candles) < 30:
                logging.debug(f"[HOLY] {symbol} → 캔들 부족")
                return None

            closes = [float(c[4]) for c in candles]
            lows = [float(c[3]) for c in candles]
            highs = [float(c[2]) for c in candles]

            ema20 = calculate_ema(closes, 20)
            if ema20 is None:
                return None

            current_price = get_price(symbol)
            if current_price is None:
                logging.debug(f"[HOLY] {symbol} → 현재가 없음")
                return None

            near_ema = abs(current_price - ema20[-1]) / ema20[-1] < 0.012  # ✅ 유지
            pullback_range = (max(highs[-5:-1]) - min(lows[-5:-1])) / closes[-1]
            pullback_ok = pullback_range > 0.008  # ✅ 유지

            if near_ema and pullback_ok:
                if closes[-2] < ema20[-2] and closes[-1] > ema20[-1]:
                    logging.info(f"[HOLY] {symbol} → 반등 인식 (long)")
                    return {"symbol": symbol, "side": "LONG"}
                elif closes[-2] > ema20[-2] and closes[-1] < ema20[-1]:
                    logging.info(f"[HOLY] {symbol} → 반락 인식 (short)")
                    return {"symbol": symbol, "side": "SHORT"}

            logging.debug(f"[HOLY] {symbol} → 조건 미충족 (pullback_ok={pullback_ok}, near_ema={near_ema})")
            return None

        except Exception as e:
            logging.error(f"[HOLY] {symbol} 진입 오류: {e}")
            return None

    def check_exit(self, symbol, entry_side):
        try:
            candles = get_candles(symbol, interval="5m", limit=30)
            if len(candles) < 2:
                return False

            closes = [float(c[4]) for c in candles]
            ema20 = calculate_ema(closes, 20)
            if ema20 is None:
                return False

            if entry_side == "LONG" and closes[-1] < ema20[-1]:
                return True
            if entry_side == "SHORT" and closes[-1] > ema20[-1]:
                return True
            return False

        except Exception as e:
            logging.error(f"[HOLY] {symbol} 청산 오류: {e}")
            return False