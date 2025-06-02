# utils.py
from decimal import Decimal, ROUND_DOWN, getcontext
import datetime
import pytz
import logging

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
    from binance_client import client
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
    from binance_client import client
    try:
        exchange_info = client.futures_exchange_info()
        symbols = [
            s["symbol"] for s in exchange_info["symbols"]
            if s["contractType"] == "PERPETUAL" and 
               s["quoteAsset"] == "USDT" and 
               s["status"] == "TRADING" and
               not s["symbol"].endswith("_PERP")  # 이상한 페어 제외
        ]
        return symbols
    except Exception as e:
        logging.error(f"get_tradable_futures_symbols 오류: {e}")
        return []

def get_tick_size(symbol: str):
    from binance_client import client
    from decimal import Decimal
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    return Decimal(str(f['tickSize']))
    return Decimal("0.01")

import pandas as pd
import numpy as np

def calculate_adx(df, period=14):
    """
    df: pandas DataFrame with columns ['high', 'low', 'close']
    period: ADX 계산 기간 (기본 14)
    
    Returns: ADX (float or pd.Series)
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

    return adx.iloc[-1]  # 최신 ADX 값 반환

import pandas as pd

def calculate_stochastic(df, k_period=14, d_period=3):
    """
    Stochastic oscillator 계산 함수
    
    df: pandas DataFrame with columns ['high', 'low', 'close']
    k_period: %K 기간 (기본 14)
    d_period: %D 기간 (기본 3)
    
    반환: %K, %D의 마지막 값 (tuple)
    """
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()

    k = 100 * ((df['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()

    return k.iloc[-1], d.iloc[-1]

import pandas as pd
import numpy as np

def calculate_rsi(df, period=14):
    """
    RSI (Relative Strength Index) 계산 함수
    
    df: pandas DataFrame with 'close' column
    period: RSI 기간 (기본 14)
    
    반환: RSI의 마지막 값 (float)
    """
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    """
    MACD (Moving Average Convergence Divergence) 계산 함수

    df: pandas DataFrame with 'close' column
    fast_period: 단기 EMA 기간 (기본 12)
    slow_period: 장기 EMA 기간 (기본 26)
    signal_period: 시그널선 EMA 기간 (기본 9)

    반환: MACD 값과 시그널 값 (tuple)
    """
    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1]

def calculate_ema_cross(df, short_period=12, long_period=26):
    """
    EMA 골든크로스/데드크로스 신호 계산

    df: pandas DataFrame with 'close' column
    short_period: 단기 EMA 기간 (기본 12)
    long_period: 장기 EMA 기간 (기본 26)

    반환: (골든크로스 발생 여부, 데드크로스 발생 여부) 튜플 (bool, bool)
    """
    ema_short = df['close'].ewm(span=short_period, adjust=False).mean()
    ema_long = df['close'].ewm(span=long_period, adjust=False).mean()

    # 현재와 직전 EMA 비교
    cross_up = (ema_short.iloc[-2] < ema_long.iloc[-2]) and (ema_short.iloc[-1] > ema_long.iloc[-1])
    cross_down = (ema_short.iloc[-2] > ema_long.iloc[-2]) and (ema_short.iloc[-1] < ema_long.iloc[-1])

    return cross_up, cross_down

def count_entry_signals(*signals):
    """
    여러 개의 진입 신호들 중 True인 개수를 반환.
    
    signals: bool 형식의 신호들 (가변인자)
    
    반환: True인 신호 개수 (int)
    """
    return sum(1 for s in signals if s)
