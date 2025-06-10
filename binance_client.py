# File: binance_client.py
from binance.client import Client
from config import Config

class BinanceClient:
    def __init__(self):
        self.client = Client(api_key=Config.BINANCE_API_KEY, api_secret=Config.BINANCE_API_SECRET)
        # set leverage for all symbols
        if Config.EXCHANGE == "binance":
            for sym in self.client.get_exchange_info()["symbols"]:
                try:
                    self.client.futures_change_leverage(symbol=sym['symbol'], leverage=Config.LEVERAGE)
                except Exception:
                    pass

    def get_klines(self, symbol, interval, limit=Config.ATR_PERIOD*3):
        return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)

    def place_order(self, symbol, side, quantity, stop_loss=None, take_profit=None):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }
        order = self.client.futures_create_order(**params)
        # attach SL/TP
        if stop_loss:
            self.client.futures_create_order(symbol=symbol, side='SELL' if side=='BUY' else 'BUY', type='STOP_MARKET', stopPrice=stop_loss, closePosition=True)
        if take_profit:
            self.client.futures_create_order(symbol=symbol, side='SELL' if side=='BUY' else 'BUY', type='TAKE_PROFIT_MARKET', stopPrice=take_profit, closePosition=True)
        return order

    def get_account_balance(self):
        return float(self.client.futures_account_balance()[0]['balance'])

    def cancel_all_sltp(self):
        orders = self.client.futures_get_open_orders()
        for o in orders:
            if o['type'] in ['TAKE_PROFIT_MARKET','STOP_MARKET']:
                try:
                    self.client.futures_cancel_order(symbol=o['symbol'], orderId=o['orderId'])
                except Exception:
                    pass
