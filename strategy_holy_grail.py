import logging
from price_ws import get_price
from utils import get_candles, calculate_ema

# --------------------------------------
# ✅ 진입 조건 조절 파라미터 (라쉬케5 기준)
# 진입 빈도와 승률 조절할 수 있음
# --------------------------------------
PULLBACK_THRESHOLD = 0.008   # 최소 눌림폭 (%), 높일수록 보수적
NEAR_EMA_RANGE = 0.012       # EMA20 근접 범위, 작을수록 보수적

class StrategyHolyGrail:
    def __init__(self, symbols):
        self.name = "HOLY_GRAIL"
        self.symbols = symbols

    def check_entry(self, symbol):
        try:
            candles = get_candles(symbol, interval="5m", limit=30)
            if len(candles) < 21:
                logging.debug(f"[HG] {symbol} → 캔들 부족")
                return None

            closes = [float(c[4]) for c in candles]
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]

            ema20 = calculate_ema(closes, 20)
            if ema20 is None:
                logging.debug(f"[HG] {symbol} → EMA 계산 실패")
                return None

            price = closes[-1]
            prev_price = closes[-2]
            ema = ema20[-1]
            prev_ema = ema20[-2]
            distance = abs(price - ema) / ema

            if distance > NEAR_EMA_RANGE:
                logging.debug(f"[HG] {symbol} → EMA20 거리 초과: distance={distance:.4f}")
                return None

            pullback_range = (max(highs[-3:-1]) - min(lows[-3:-1])) / ema
            if pullback_range < PULLBACK_THRESHOLD:
                logging.debug(f"[HG] {symbol} → pullback 부족: range={pullback_range:.4f}")
                return None

            # 롱 조건: EMA 위에서 반등
            if prev_price < prev_ema and price > ema:
                logging.info(f"[HG] {symbol} → 반등 (long)")
                return {"symbol": symbol, "side": "LONG"}

            # 숏 조건: EMA 아래서 반락
            if prev_price > prev_ema and price < ema:
                logging.info(f"[HG] {symbol} → 반락 (short)")
                return {"symbol": symbol, "side": "SHORT"}

            logging.debug(f"[HG] {symbol} → 반등/반락 조건 미충족")
            return None

        except Exception as e:
            logging.error(f"[HG] {symbol} 진입 오류: {e}")
            return None

    def check_exit(self, symbol, entry_side):
        try:
            candles = get_candles(symbol, interval="5m", limit=30)
            if len(candles) < 21:
                return False

            closes = [float(c[4]) for c in candles]
            ema20 = calculate_ema(closes, 20)
            if ema20 is None:
                return False

            price = closes[-1]
            ema = ema20[-1]

            if entry_side == "LONG" and price < ema:
                return True
            if entry_side == "SHORT" and price > ema:
                return True
            return False

        except Exception as e:
            logging.error(f"[HG] {symbol} 청산 오류: {e}")
            return False
