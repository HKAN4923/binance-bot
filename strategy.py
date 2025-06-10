import pandas as pd
import numpy as np
from binance_client import BinanceClient
from config import Config

class ATRBreakoutStrategy:
    def __init__(self, client: BinanceClient):
        self.client = client

    def calculate_atr(self, data: pd.DataFrame):
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(Config.ATR_PERIOD).mean()
        return atr

    def generate_signals(self, symbol: str):
        klines = self.client.get_klines(symbol, Config.BREAKOUT_TF)
        df = pd.DataFrame(klines, columns=['open_time','open','high','low','close','volume','close_time','x','y','z','w','q'])
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        atr = self.calculate_atr(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        entry_price = prev['high'] + Config.ENTRY_MULTIPLIER * atr.iloc[-2]
        exit_price = prev['low'] - Config.EXIT_MULTIPLIER * atr.iloc[-2]
        if last['close'] > entry_price:
            return {'side':'BUY', 'price': last['close'], 'sl': last['close'] - Config.SLTP_RATIO* (last['close']-exit_price), 'tp': last['close'] + Config.SLTP_RATIO*(last['close']-exit_price)}
        elif last['close'] < exit_price:
            return {'side':'SELL', 'price': last['close'], 'sl': last['close'] + Config.SLTP_RATIO*(entry_price-last['close']), 'tp': last['close'] - Config.SLTP_RATIO*(entry_price-last['close'])}
        return None
