import os
import time
import math
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from dotenv import load_dotenv
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange

# Load environment variables
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Initialize Binance client
client = Client(API_KEY, API_SECRET)

# Settings
BALANCE_USDT = 100
LEVERAGE = 10
RISK_RATIO = 0.3
MAX_POSITIONS = 3
ANALYSIS_INTERVAL = 1        # seconds
REANALYSIS_INTERVAL = 60     # seconds
TELEGRAM_SUMMARY_INTERVAL = 1800  # seconds
MIN_ADX = 20
ATR_PERIOD = 14
OSC_PERIOD = 14
EMA_PERIOD = 20
RSI_PERIOD = 14
RR_RATIO = 1.3
TIMEOUT1 = timedelta(hours=2, minutes=30)
TIMEOUT2 = timedelta(hours=3)

# State
positions = {}  # symbol -> {side, entry_time, qty}
last_summary = datetime.now(timezone.utc) - timedelta(seconds=TELEGRAM_SUMMARY_INTERVAL)

# Static list of top 100 symbols (example)
TRADE_SYMBOLS = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','AVAXUSDT','MATICUSDT','DOTUSDT',
    'SHIBUSDT','LTCUSDT','TRXUSDT','LINKUSDT','UNIUSDT','BCHUSDT','XLMUSDT','ATOMUSDT','VETUSDT','LUNCUSDT',
    'ICPUSDT','FILUSDT','EGLDUSDT','EOSUSDT','AAVEUSDT','BSVUSDT','XTZUSDT','THETAUSDT','HBARUSDT','AXSUSDT',
    'MKRUSDT','GRTUSDT','KLAYUSDT','NEARUSDT','FTMUSDT','SANDUSDT','ENJUSDT','AXSUSDT','CAKEUSDT','CHZUSDT',
    'APEUSDT','STXUSDT','RUNEUSDT','FLOWUSDT','VTHOUSDT','GALAUSDT','MANAUSDT','KAVAUSDT','IMXUSDT','CELRUSDT',
    'ZILUSDT','CELOUSDT','ARUSDT','SUSHIUSDT','COMPUSDT','SNXUSDT','DASHUSDT','LDOUSDT','USTCUSDT','AVAXUSDT',
    'GALAAUSDT','CVXUSDT','NEOUSDT','WAVESUSDT','XMRUSDT','OMGUSDT','QTUMUSDT','ZRXUSDT','BATUSDT','NANOUSDT',
    'DGBUSDT','RENUSDT','KNCUSDT','BATUSDT','ONTUSDT','ICXUSDT','ZECUSDT','FTTUSDT','GNOUSDT','BNTUSDT',
    'CELOUSDT','ARBUSDT','ONTUSDT','QTUMUSDT','ZRXUSDT','BATUSDT','NEOUSDT','ENJUSDT','GRTUSDT','KNCUSDT'
]

# Utility functions

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg
        })
    except:
        pass


def fetch_klines(symbol, interval, limit=100):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    df[['o','h','l','c']] = df[['o','h','l','c']].astype(float)
    df['t'] = pd.to_datetime(df['t'], unit='ms')
    return df


def calc_indicators(df):
    df['rsi'] = RSIIndicator(df['c'], RSI_PERIOD).rsi()
    df['macd_diff'] = MACD(df['c']).macd_diff()
    df['ema'] = EMAIndicator(df['c'], EMA_PERIOD).ema_indicator()
    df['adx'] = ADXIndicator(df['h'], df['l'], df['c'], window=RSI_PERIOD).adx()
    df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=OSC_PERIOD).stoch()
    df['atr'] = AverageTrueRange(df['h'], df['l'], df['c'], window=ATR_PERIOD).average_true_range()
    return df.dropna()


def get_price_tick(symbol):
    info = client.futures_exchange_info()['symbols']
    for s in info:
        if s['symbol'] == symbol:
            return float(next(f['tickSize'] for f in s['filters'] if f['filterType']=='PRICE_FILTER'))
    return 0.01


def round_price(symbol, price):
    tick = get_price_tick(symbol)
    prec = int(-math.log(tick,10))
    return round(price, prec)


def round_qty(symbol, qty):
    info = client.futures_exchange_info()['symbols']
    for s in info:
        if s['symbol']==symbol:
            step = float(next(f['stepSize'] for f in s['filters'] if f['filterType']=='LOT_SIZE'))
            prec = int(-math.log(step,10))
            return float(f"{qty:.{prec}f}")
    return qty

# Entry signal

def check_entry(symbol):
     df = fetch_klines(symbol, '1h')
    if df.empty:
        return None
    df = calc_indicators(df)
    if df.empty:
        return None
    last = df.iloc[-1]
    df = calc_indicators(fetch_klines(symbol, '1h'))
    last = df.iloc[-1]
    if last['adx'] < MIN_ADX:
        return None
    long_score = sum([last['rsi']<40, last['macd_diff']>0, last['c']>last['ema'], last['stoch']<20])
    short_score = sum([last['rsi']>60, last['macd_diff']<0, last['c']<last['ema'], last['stoch']>80])
    core_long = sum([last['macd_diff']>0, last['c']>last['ema'], last['adx']>MIN_ADX])
    core_short = sum([last['macd_diff']<0, last['c']<last['ema'], last['adx']>MIN_ADX])
    if core_long >= 2 and long_score >= 3:
        return 'LONG'
    if core_short >= 2 and short_score >= 3:
        return 'SHORT'
    return None

# Enter trade
def enter(symbol, side):
    price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    atr = calc_indicators(fetch_klines(symbol, '1h'))['atr'].iloc[-1]
    tick = get_price_tick(symbol)
    min_diff = tick * 5
    if side == 'LONG':
        sl = min(price - atr, price - min_diff)
        tp = max(price + atr * RR_RATIO, price + min_diff)
    else:
        sl = max(price + atr, price + min_diff)
        tp = min(price - atr * RR_RATIO, price - min_diff)
    sl, tp = round_price(symbol, sl), round_price(symbol, tp)
    qty = BALANCE_USDT * RISK_RATIO * LEVERAGE / price
    qty = round_qty(symbol, qty)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    client.futures_create_order(symbol=symbol, side=SIDE_BUY if side=='LONG' else SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=qty)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY, type="TAKE_PROFIT_MARKET", stopPrice=tp, closePosition=True)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY, type="STOP_MARKET", stopPrice=sl, closePosition=True)
    positions[symbol] = {'side':side, 'entry_time':datetime.now(timezone.utc), 'qty':qty}
    send_telegram(f"[ENTRY] {symbol} {side}@{price:.2f} TP={tp} SL={sl}")

# Manage positions
def manage():
    now = datetime.now(timezone.utc)
    for sym, pos in list(positions.items()):
        age = now - pos['entry_time']
        # strong reverse signal\	fp
        df5 = calc_indicators(fetch_klines(sym, '5m'))
        last5 = df5.iloc[-1]
        rev = sum([last5['rsi']>50 if pos['side']=='LONG' else last5['rsi']<50,
                   last5['macd_diff']<0 if pos['side']=='LONG' else last5['macd_diff']>0,
                   last5['c']<last5['ema'] if pos['side']=='LONG' else last5['c']>last5['ema'],
                   last5['stoch']>50 if pos['side']=='LONG' else last5['stoch']<50])
        if rev >= 3:
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"[STRONG EXIT] {sym} rev={rev}")
            del positions[sym]
            continue
        if age >= TIMEOUT2:
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"[TIME EXIT] {sym} 3h")
            del positions[sym]
        elif age >= TIMEOUT1:
            entry_price = float(client.futures_position_information(symbol=sym)[0]['entryPrice'])
            curr = float(client.futures_symbol_ticker(symbol=sym)['price'])
            pnl = (curr-entry_price)*pos['qty'] if pos['side']=='LONG' else (entry_price-curr)*pos['qty']
            if pnl > 0:
                client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=pos['qty'])
                send_telegram(f"[PROFIT EXIT] {sym} pnl={pnl}")
                del positions[sym]
            else:
                df1 = calc_indicators(fetch_klines(sym, '1h')).iloc[-1]
                score = sum([df1['rsi']<40 if pos['side']=='LONG' else df1['rsi']>60,
                             df1['macd_diff']>0 if pos['side']=='LONG' else df1['macd_diff']<0,
                             df1['c']>df1['ema'] if pos['side']=='LONG' else df1['c']<df1['ema'],
                             df1['stoch']<20 if pos['side']=='LONG' else df1['stoch']>80])
                if score < 3:
                    client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=pos['qty'])
                    send_telegram(f"[REEXIT] {sym} score={score}")
                    del positions[sym]

# Summary
def summary():
    global last_summary
    now = datetime.now(timezone.utc)
    if (now-last_summary).total_seconds() >= TELEGRAM_SUMMARY_INTERVAL:
        msgs = [f"{s}:{positions[s]['side']} q={positions[s]['qty']}" for s in positions]
        send_telegram("[SUMMARY]\n"+"\n".join(msgs))
        last_summary = now

# Main loop
def main():
    while True:
        summary()
        for symbol in TRADE_SYMBOLS:
            if len(positions) < MAX_POSITIONS and symbol not in positions:
                side = check_entry(symbol)
                if side:
                    enter(symbol, side)
        manage()
        time.sleep(ANALYSIS_INTERVAL)

if __name__ == '__main__':
    main()
