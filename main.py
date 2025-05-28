import os
import time
import math
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

# Load environment variables
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

client = Client(API_KEY, API_SECRET)

# Settings
USDT_BALANCE = 100
LEVERAGE = 10
MARGIN_RATE = 0.3            # 30% of balance per position
TP_SL_SL_PERCENT = 0.01     # 1% initial stop-loss
RR_RATIO = 1.3              # risk-reward
MAX_POSITIONS = 3
TIMEOUT_1 = timedelta(hours=2, minutes=30)
TIMEOUT_2 = timedelta(hours=3)
TELEGRAM_INTERVAL = 600     # seconds
ANALYSIS_INTERVAL = 1       # seconds

# State
positions = {}  # symbol -> position info
last_telegram = datetime.utcnow() - timedelta(seconds=TELEGRAM_INTERVAL)

# Helpers
def send_telegram(msg):
    global last_telegram
    now = datetime.utcnow()
    if (now - last_telegram).total_seconds() >= TELEGRAM_INTERVAL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        last_telegram = now


def get_tick_size(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    return float(f['tickSize'])
    return 0.01


def get_lot_size(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    return float(f['stepSize'])
    return 0.001


def round_price(price, tick_size):
    return float(format(round(price / tick_size) * tick_size, f".{abs(int(math.log10(tick_size)))}f"))


def round_qty(qty, step_size):
    precision = abs(int(math.log10(step_size)))
    return float(format(math.floor(qty / step_size) * step_size, f".{precision}f"))


def get_price(symbol):
    return float(client.futures_mark_price(symbol=symbol)['markPrice'])

# Trade logic (simple signal placeholder)
def signal_generator(symbol):
    # implement 30m/1h indicator logic here
    return None

# Enter trade with TP/SL orders
def enter_trade(symbol, side):
    if len(positions) >= MAX_POSITIONS or symbol in positions:
        return
    # Calculate quantity
    bal = USDT_BALANCE
    margin = bal * MARGIN_RATE
    notional = margin * LEVERAGE
    price = get_price(symbol)
    raw_qty = notional / price
    step_size = get_lot_size(symbol)
    qty = round_qty(raw_qty, step_size)
    if qty <= 0:
        return
    # Place market entry
    order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    client.futures_create_order(symbol=symbol, side=order_side, type=ORDER_TYPE_MARKET, quantity=qty)
    # Calculate SL and TP
    sl_price = price * (1 - TP_SL_SL_PERCENT) if side == 'LONG' else price * (1 + TP_SL_SL_PERCENT)
    rr_dist = abs(price - sl_price) * RR_RATIO
    tp_price = price + rr_dist if side == 'LONG' else price - rr_dist
    # Round prices
    tick_size = get_tick_size(symbol)
    sl_price = round_price(sl_price, tick_size)
    tp_price = round_price(tp_price, tick_size)
    # Place TP and SL orders
    close_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
    client.futures_create_order(symbol=symbol, side=close_side, type='TAKE_PROFIT_MARKET', stopPrice=tp_price, closePosition=True)
    client.futures_create_order(symbol=symbol, side=close_side, type='STOP_MARKET', stopPrice=sl_price, closePosition=True)
    # Record position
    positions[symbol] = {
        'side': side,
        'entry_price': price,
        'qty': qty,
        'entry_time': datetime.utcnow()
    }
    send_telegram(f"Enter {symbol} {side}@{price:.2f}, TP@{tp_price:.2f}, SL@{sl_price:.2f}")

# Monitor and time-based exit
def manage_positions():
    now = datetime.utcnow()
    for sym, pos in list(positions.items()):
        elapsed = now - pos['entry_time']
        # Time-based conditions
        if elapsed >= TIMEOUT_2:
            # force close
            close_market(sym, pos)
        elif elapsed >= TIMEOUT_1:
            # if still open, do nothing (TP/SL orders exist)
            pass


def close_market(symbol, pos):
    side = SIDE_SELL if pos['side']=='LONG' else SIDE_BUY
    client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=pos['qty'])
    send_telegram(f"TimeExit {symbol} PnL unknown")
    del positions[symbol]

# Main loop
SYMBOLS = [s['symbol'] for s in client.futures_exchange_info()['symbols'] if s['contractType']=='PERPETUAL']

def main():
    while True:
        # Check for new signals
        for symbol in SYMBOLS:
            if len(positions) < MAX_POSITIONS and symbol not in positions:
                sig = signal_generator(symbol)
                if sig:
                    enter_trade(symbol, sig)
        # Manage existing positions
        manage_positions()
        time.sleep(ANALYSIS_INTERVAL)

if __name__=='__main__':
    main()
