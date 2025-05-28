import os
import time
import math
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
import requests
import logging

# Load environment variables
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not API_KEY or not API_SECRET:
    raise SystemExit('Error: Missing Binance API credentials')

client = Client(API_KEY, API_SECRET)

# Settings
RR_RATIO = 1.3
LEVERAGE = 10
ANALYSIS_INTERVAL = 1      # seconds
TELEGRAM_INTERVAL = 600    # seconds (10 minutes)
MAX_CONCURRENT = 3         # up to 3 simultaneous positions
MARGIN_RATE = 0.3         # 30% of balance as margin per position
TIMEOUT_1 = 2.5 * 3600    # 2.5 hours in seconds
TIMEOUT_2 = 3 * 3600      # 3 hours
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

# Logging
logging.basicConfig(filename='trade_log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')
def log(msg): print(msg); logging.info(msg)

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")

# Data fetch & indicators
def fetch_klines(symbol, interval):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=100)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"]).astype(float)
    return df

def get_df(symbol, interval):
    try:
        df = fetch_klines(symbol, interval)
        df['rsi'] = RSIIndicator(df['c'], window=14).rsi()
        df['macd'] = MACD(df['c']).macd_diff()
        df['ema9'] = EMAIndicator(df['c'], window=9).ema_indicator()
        df['adx'] = ADXIndicator(df['h'], df['l'], df['c'], window=14).adx()
        df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=14).stoch()
        return df.dropna()
    except Exception as e:
        log(f"get_df error {symbol} {interval}: {e}")
        return None

# Signal logic
def check_signal(df):
    last = df.iloc[-1]
    if last['adx'] < 10: return None
    score_long=0; score_short=0
    if last['rsi']<45: score_long+=1
    if last['rsi']>55: score_short+=1
    if last['macd']>0: score_long+=1
    if last['macd']<0: score_short+=1
    if last['c']>last['ema9']: score_long+=1
    if last['c']<last['ema9']: score_short+=1
    if last['stoch']<60: score_long+=1
    if last['stoch']>40: score_short+=1
    return 'LONG' if score_long>=3 else ('SHORT' if score_short>=3 else None)

# Position management
positions = []  # tracking open positions

class Position:
    def __init__(self, symbol, side, entry_price, qty, entry_time):
        self.symbol=symbol; self.side=side; self.entry_price=entry_price; self.qty=qty; self.entry_time=entry_time

# Calculate qty based on margin rate and leverage
def calc_qty(symbol, side):
    bal = float([b['balance'] for b in client.futures_account_balance() if b['asset']=='USDT'][0])
    margin = bal * MARGIN_RATE
    notional = margin * LEVERAGE
    price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    qty = notional / price
    return qty

# Enter trade

def enter_trade(symbol, side):
    qty = calc_qty(symbol, side)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    order_side=SIDE_BUY if side=='LONG' else SIDE_SELL
    client.futures_create_order(symbol=symbol, side=order_side, type=ORDER_TYPE_MARKET, quantity=qty)
    entry_price=float(client.futures_mark_price(symbol=symbol)['markPrice'])
    log(f"Enter {symbol} {side}@{entry_price:.2f}")
    send_telegram(f"Enter {symbol} {side}@{entry_price:.2f}")
    positions.append(Position(symbol, side, entry_price, qty, time.time()))

# Exit trade

def exit_trade(pos):
    exit_side = SIDE_SELL if pos.side=='LONG' else SIDE_BUY
    client.futures_create_order(symbol=pos.symbol, side=exit_side, type=ORDER_TYPE_MARKET, quantity=pos.qty)
    price=float(client.futures_mark_price(symbol=pos.symbol)['markPrice'])
    pnl = (price-pos.entry_price)/pos.entry_price*100 if pos.side=='LONG' else (pos.entry_price-price)/pos.entry_price*100
    log(f"Exit {pos.symbol} {pos.side}@{price:.2f} PnL:{pnl:.2f}%")
    send_telegram(f"Exit {pos.symbol} PnL:{pnl:.2f}%")
    positions.remove(pos)

# Monitoring & management
def manage_positions():
    now=time.time()
    for pos in positions.copy():
        elapsed = now - pos.entry_time
        price=float(client.futures_mark_price(symbol=pos.symbol)['markPrice'])
        pnl=(price-pos.entry_price)/pos.entry_price*100 if pos.side=='LONG' else (pos.entry_price-price)/pos.entry_price*100
        # If >2.5h
        if elapsed>=TIMEOUT_1:
            if pnl>0:
                exit_trade(pos)
            else:
                # check 5m signal for continuation
                df5=get_df(pos.symbol,'5m')
                sig5=check_signal(df5) if df5 is not None else None
                if sig5==pos.side and elapsed<TIMEOUT_2:
                    pass
                else:
                    exit_trade(pos)
        elif elapsed>=TIMEOUT_2:
            exit_trade(pos)

# Main loop

def main():
    send_telegram("Bot started")
    last_telegram=time.time()
    while True:
        # Entry: if capacity available
        if len(positions)<MAX_CONCURRENT:
            for sym in SYMBOLS:
                if len(positions)>=MAX_CONCURRENT: break
                df30=get_df(sym,'30m'); df1h=get_df(sym,'1h')
                if df30 is None or df1h is None: continue
                sig30=check_signal(df30); sig1h=check_signal(df1h)
                sig=sig30 if sig30==sig1h else (sig30 or sig1h)
                if sig:
                    enter_trade(sym, sig)
                    break
        # Manage open positions
        manage_positions()
        # Periodic telegram
        if time.time()-last_telegram>=TELEGRAM_INTERVAL:
            for pos in positions:
                price=float(client.futures_mark_price(symbol=pos.symbol)['markPrice'])
                pnl=(price-pos.entry_price)/pos.entry_price*100 if pos.side=='LONG' else (pos.entry_price-price)/pos.entry_price*100
                send_telegram(f"Status {pos.symbol}: PnL:{pnl:.2f}%")
            last_telegram=time.time()
        time.sleep(ANALYSIS_INTERVAL)

if __name__=='__main__':
    main()
