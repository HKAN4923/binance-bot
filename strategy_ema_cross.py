import logging
from utils import get_candles, calculate_ema, calculate_rsi

# --------------------------------------
# ✅ 진입 조건 조절 파라미터 (라쉬케5 전략 기준)
# 전략 민감도 및 승률 조정 시 이곳 조정
# --------------------------------------
USE_RSI_FILTER = True        # RSI 필터 사용 여부
RSI_LONG_MIN = 55            # 롱 진입 RSI 최소값
RSI_SHORT_MAX = 45           # 숏 진입 RSI 최대값

class StrategyEMACross:
    def __init__(self, symbols):
        self.name = "EMA"
        self.symbols = symbols

    def check_entry(self, symbol):
        try:
            candles = get_candles(symbol, interval="5m", limit=50)
            if len(candles) < 21:
                logging.debug(f"[EMA] {symbol} → 캔들 부족")
                return None

            closes = [float(c[4]) for c in candles]
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)

            if ema9 is None or ema21 is None:
                logging.debug(f"[EMA] {symbol} → EMA 계산 실패")
                return None

            # ✅ RSI 필터
            latest_rsi = None
            if USE_RSI_FILTER:
                rsi = calculate_rsi(closes, 14)
                if rsi is None or len(rsi) == 0:
                    logging.debug(f"[EMA] {symbol} → RSI 계산 실패")
                    return None
                latest_rsi = rsi[-1]

            prev_ema9, curr_ema9 = ema9[-2], ema9[-1]
            prev_ema21, curr_ema21 = ema21[-2], ema21[-1]

            # 골든크로스
            if prev_ema9 < prev_ema21 and curr_ema9 > curr_ema21:
                if USE_RSI_FILTER and latest_rsi < RSI_LONG_MIN:
                    logging.debug(f"[EMA] {symbol} → RSI {latest_rsi:.1f} < {RSI_LONG_MIN} (long 제한)")
                    return None
                logging.info(f"[EMA] {symbol} → 골든크로스 (long)")
                return {"symbol": symbol, "side": "LONG"}

            # 데드크로스
            if prev_ema9 > prev_ema21 and curr_ema9 < curr_ema21:
                if USE_RSI_FILTER and latest_rsi > RSI_SHORT_MAX:
                    logging.debug(f"[EMA] {symbol} → RSI {latest_rsi:.1f} > {RSI_SHORT_MAX} (short 제한)")
                    return None
                logging.info(f"[EMA] {symbol} → 데드크로스 (short)")
                return {"symbol": symbol, "side": "SHORT"}

            return None

        except Exception as e:
            logging.error(f"[EMA] {symbol} 진입 오류: {e}")
            return None

    def check_exit(self, symbol, entry_side):
        try:
            candles = get_candles(symbol, interval="5m", limit=50)
            if len(candles) < 21:
                return False

            closes = [float(c[4]) for c in candles]
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)

            if ema9 is None or ema21 is None:
                return False

            curr_ema9 = ema9[-1]
            curr_ema21 = ema21[-1]

            if entry_side == "LONG" and curr_ema9 < curr_ema21:
                return True
            if entry_side == "SHORT" and curr_ema9 > curr_ema21:
                return True
            return False

        except Exception as e:
            logging.error(f"[EMA] {symbol} 청산 오류: {e}")
            return False
