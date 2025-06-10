import time
from binance_client import BinanceClient
from strategy import ATRBreakoutStrategy
from utils import calculate_quantity
from telegram_notifier import send_position_alert, send_position_close, send_error_alert
from config import Config

client = BinanceClient()
strategy = ATRBreakoutStrategy(client)

symbols = [s['symbol'] for s in client.client.get_ticker_24hr() if s['symbol'].endswith("USDT")][:100]

open_positions = {}

def run_bot():
    while True:
        try:
            for symbol in symbols:
                if len(open_positions) >= Config.MAX_POSITIONS:
                    continue

                if symbol in open_positions:
                    continue

                signal = strategy.generate_signals(symbol)
                if signal:
                    side = signal['side']
                    entry_price = signal['price']
                    sl_price = signal['sl']
                    tp_price = signal['tp']
                    balance = client.get_account_balance()
                    quantity = calculate_quantity(symbol, balance)

                    if quantity == 0:
                        continue

                    order = client.place_order(symbol, side, quantity, stop_loss=sl_price, take_profit=tp_price)
                    open_positions[symbol] = {
                        'side': side,
                        'entry': entry_price,
                        'sl': sl_price,
                        'tp': tp_price,
                        'qty': quantity,
                        'time': time.time()
                    }
                    send_position_alert(symbol, side, quantity, entry_price, sl_price, tp_price)

            closed = []
            for symbol, data in open_positions.items():
                current_price = float(client.client.futures_mark_price(symbol=symbol)['markPrice'])
                side = data['side']

                if side == 'BUY' and (current_price <= data['sl'] or current_price >= data['tp']):
                    closed.append(symbol)
                elif side == 'SELL' and (current_price >= data['sl'] or current_price <= data['tp']):
                    closed.append(symbol)

            for symbol in closed:
                send_position_close(symbol, open_positions[symbol]['side'], open_positions[symbol]['qty'])
                del open_positions[symbol]

            time.sleep(30)

        except Exception as e:
            send_error_alert(f"Bot Error: {str(e)}")
            time.sleep(60)

if __name__ == '__main__':
    run_bot()
