import pandas as pd
from binance_client import get_klines
from config import USDT_RISK_PER_TRADE, LEVERAGE

def calculate_quantity(symbol):
    df = get_klines(symbol, '1m', limit=1)
    if df is None or df.empty:
        return 0.0
    price = df['close'].iloc[-1]
    quantity = (USDT_RISK_PER_TRADE * LEVERAGE) / price
    return round(quantity, 3)
