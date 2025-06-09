
# utils.py
import pandas as pd
from binance_client import get_klines
from config import USDT_RISK_PER_TRADE, LEVERAGE

# ✅ ATR 계산 (Average True Range)
def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

# ✅ 수량 계산 (현재가 기준 USDT 리스크에 따른 계약 수량)
def calculate_quantity(symbol):
    df = get_klines(symbol, '1m', limit=1)
    if df is None or df.empty:
        return 0.0
    price = df['close'].iloc[-1]
    quantity = (USDT_RISK_PER_TRADE * LEVERAGE) / price
    return round(quantity, 3)