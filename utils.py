from decimal import Decimal, ROUND_DOWN, getcontext
import datetime
import pytz
import logging
import pandas as pd
import numpy as np
from binance_client import client  # 이미 binance_client.py에서 Client를 정의해 두었으므로 직접 임포트

def to_kst(ts: float):
    utc_dt = datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC)
    return utc_dt.astimezone(pytz.timezone("Asia/Seoul"))

def calculate_qty(balance: float, price: float, leverage: int, fraction: float, qty_precision: int, min_qty: float):
    getcontext().prec = qty_precision + 10
    raw = Decimal(balance) * Decimal(leverage) * Decimal(fraction) / Decimal(price)
    quant = Decimal(f"1e-{qty_precision}")
    qty = raw.quantize(quant, rounding=ROUND_DOWN)
    
    # 최대 포지션 크기 제한 (잔고 2% 이하)
    max_qty = Decimal(balance) * Decimal("0.02") / Decimal(price)
    qty = min(qty, max_qty)
    
    if qty < Decimal(str(min_qty)):
        return 0.0
    return float(qty)

def get_top_100_volume_symbols():
    try:
        stats_24h = client.futures_ticker()
        usdt_pairs = [
            {"symbol": s["symbol"], "volume": float(s["quoteVolume"])}
            for s in stats_24h if s["symbol"].endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
        return [s["symbol"] for s in usdt_pairs[:100]]
    except Exception as e:
        logging.error(f"get_top_100_volume_symbols 오류: {e}")
        return []

def get_tradable_futures_symbols():
    try:
        exchange_info = client.futures_exchange_info()
        symbols = [
            s["symbol"] for s in exchange_info["symbols"]
            if s["contractType"] == "PERPETUAL" and 
               s["quoteAsset"] == "USDT" and 
               s["status"] == "TRADING" and
               not s["symbol"].endswith("_PERP")
        ]
        return symbols
    except Exception as e:
        logging.error(f"get_tradable_futures_symbols 오류: {e}")
        return []

def get_tick_size(symbol: str):
    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        return Decimal(str(f['tickSize']))
        return Decimal("0.01")
    except Exception as e:
        logging.error(f"get_tick_size 오류: {e}")
        return Decimal("0.01")

# -------------------------
# 지표 계산 함수 모음
# -------------------------

def calculate_rsi(df: pd.DataFrame, period: int = 14):
    """
    RSI (Relative Strength Index) 계산 함수
    df: pandas DataFrame with 'close' column
    period: RSI 기간 (기본 14)
    반환: df에 'rsi' 컬럼 추가
    """
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi

def calculate_macd(df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
    """
    MACD (Moving Average Convergence Divergence) 계산 함수
    df: pandas DataFrame with 'close' column
    fast_period: 단기 EMA 기간 (기본 12)
    slow_period: 장기 EMA 기간 (기본 26)
    signal_period: 시그널선 EMA 기간 (기본 9)
    반환: df에 'macd', 'macd_signal', 'macd_hist' 컬럼 추가
    """
    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - signal_line

    df['macd'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_hist'] = hist

def calculate_ema_cross(df: pd.DataFrame, short_period: int = 12, long_period: int = 26):
    """
    EMA Cross 계산
    df: pandas DataFrame with 'close' column
    short_period: 단기 EMA 기간
    long_period: 장기 EMA 기간
    반환: df에 'ema_short', 'ema_long' 컬럼 추가
    """
    df['ema_short'] = df['close'].ewm(span=short_period, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=long_period, adjust=False).mean()

def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    """
    Stochastic oscillator 계산
    df: pandas DataFrame with ['high','low','close']
    k_period: %K 기간 (기본 14)
    d_period: %D 기간 (기본 3)
    반환: df에 '%K', '%D' 컬럼 추가
    """
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    df['%K'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
    df['%D'] = df['%K'].rolling(window=d_period).mean()

def calculate_adx(df: pd.DataFrame, period: int = 14):
    """
    ADX (Average Directional Index) 계산
    df: pandas DataFrame with ['high','low','close']
    period: ADX 기간 (기본 14)
    반환: df에 '+DI', '-DI', 'ADX' 컬럼 추가
    """
    high = df['high']
    low = df['low']
    close = df['close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()

    plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()

    df['+DI'] = plus_di
    df['-DI'] = minus_di
    df['ADX'] = adx

def calculate_atr(df: pd.DataFrame, period: int = 14):
    """
    ATR (Average True Range) 계산
    df: pandas DataFrame with ['high','low','close']
    period: ATR 기간 (기본 14)
    반환: pandas Series 형태의 ATR
    """
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def count_entry_signals(df: pd.DataFrame):
    """
    compute_all_signals를 이용해 df에서 long/short 신호 개수를 반환
    반환: (long_count, short_count)
    """
    signals = compute_all_signals(df)
    long_count = sum(1 for v in signals.values() if v == 'long')
    short_count = sum(1 for v in signals.values() if v == 'short')
    return long_count, short_count

# 예시로 compute_all_signals는 strategy.py에 정의되어 있기 때문에 여기선 선언만 해둠
# (실제 구현은 strategy.py에) 
def compute_all_signals(df: pd.DataFrame):
    raise NotImplementedError("compute_all_signals should be implemented in strategy.py")
