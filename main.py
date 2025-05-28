import os
import time
import math
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from dotenv import load_dotenv
from ta.momentum import RSIIndicator, StochasticOscillator, StochRSIIndicator, WilliamsRIndicator
from ta.trend import EMAIndicator, MACD, ADXIndicator, CCIIndicator
from ta.volatility import AverageTrueRange

# Load environment variables
load_dotenv()
API_KEY          = os.getenv("BINANCE_API_KEY")
API_SECRET       = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Initialize Binance client
client = Client(API_KEY, API_SECRET)

# Settings
LEVERAGE                  = 10
RISK_RATIO                = 0.3
MAX_POSITIONS             = 3
ANALYSIS_INTERVAL         = 10
MONITOR_INTERVAL          = 1
TELEGRAM_SUMMARY_INTERVAL = 1800
MONITOR_TERMINAL_INTERVAL = 30
MIN_ADX                   = 20
ATR_PERIOD                = 14
OSC_PERIOD                = 14
EMA_SHORT                 = 9
EMA_LONG                  = 21
RSI_PERIOD                = 14
RR_RATIO                  = 1.3
TIMEOUT1                  = timedelta(hours=2, minutes=30)
TIMEOUT2                  = timedelta(hours=3)
EARLY_EXIT_PCT            = 0.01

positions    = {}
last_summary = datetime.now(timezone.utc) - timedelta(seconds=TELEGRAM_SUMMARY_INTERVAL)

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": str(TELEGRAM_CHAT_ID), "text": str(msg), "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

def get_usdt_balance():
    for asset in client.futures_account_balance():
        if asset['asset'] == 'USDT':
            return float(asset['withdrawAvailable'])
    return 0.0

def get_all_usdt_symbols():
    info = client.futures_exchange_info()
    return [s['symbol'] for s in info['symbols'] if s['contractType']=='PERPETUAL' and s['quoteAsset']=='USDT']

TRADE_SYMBOLS = get_all_usdt_symbols()

def fetch_klines(symbol, interval, limit=100):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    df[['o','h','l','c']] = df[['o','h','l','c']].astype(float)
    df['t'] = pd.to_datetime(df['t'], unit='ms')
    df.set_index('t', inplace=True)
    return df

def calc_indicators(df):
    req = max(ATR_PERIOD, OSC_PERIOD, EMA_LONG, RSI_PERIOD)
    if df is None or len(df) < req:
        return pd.DataFrame()
    df['rsi']       = RSIIndicator(df['c'], RSI_PERIOD).rsi()
    df['macd_diff'] = MACD(df['c']).macd_diff()
    df['ema']       = EMAIndicator(df['c'], EMA_LONG).ema_indicator()
    df['adx']       = ADXIndicator(df['h'], df['l'], df['c'], window=RSI_PERIOD).adx()
    df['stoch']     = StochasticOscillator(df['h'], df['l'], df['c'], window=OSC_PERIOD).stoch()
    df['atr']       = AverageTrueRange(df['h'], df['l'], df['c'], window=ATR_PERIOD).average_true_range()
    df['cci']       = CCIIndicator(df['h'], df['l'], df['c'], window=OSC_PERIOD).cci()
    df['ema9']      = EMAIndicator(df['c'], EMA_SHORT).ema_indicator()
    df['ema21']     = EMAIndicator(df['c'], EMA_LONG).ema_indicator()
    df['stochrsi']  = StochRSIIndicator(df['c'], window=RSI_PERIOD).stochrsi()
    df['wpr']       = WilliamsRIndicator(df['h'], df['l'], df['c'], lbp=14).williams_r()
    return df.dropna()

def check_entry(symbol):
    df = fetch_klines(symbol, '1h')
    if df.empty: return None
    df = calc_indicators(df)
    if df.empty or df['adx'].iloc[-1] < MIN_ADX: return None
    last = df.iloc[-1]
    ls = sum([last['rsi']<40, last['macd_diff']>0, last['c']>last['ema'], last['stoch']<20])
    ss = sum([last['rsi']>60, last['macd_diff']<0, last['c']<last['ema'], last['stoch']>80])
    cl = sum([last['macd_diff']>0, last['c']>last['ema'], last['adx']>MIN_ADX])
    cs = sum([last['macd_diff']<0, last['c']<last['ema'], last['adx']>MIN_ADX])
    if cl>=2 and ls>=3: return 'LONG'
    if cs>=2 and ss>=3: return 'SHORT'
    return None

def is_early_exit(df, pos):
    last = df.iloc[-1]
    pnl_pct = ((last['c']-pos['entry_price'])/pos['entry_price']*100) if pos['side']=='LONG' else ((pos['entry_price']-last['c'])/pos['entry_price']*100)
    if pnl_pct < EARLY_EXIT_PCT*100: return False
    if pos['side']=='LONG' and (last['cci']<100 or last['ema9']<last['ema21'] or last['wpr']>-20): return True
    if pos['side']=='SHORT' and (last['cci']>-100 or last['ema9']>last['ema21'] or last['wpr']<-80): return True
    return False

def cancel_tp_sl(symbol):
    try:
        orders = client.futures_get_open_orders(symbol=symbol)
        for o in orders:
            client.futures_cancel_order(symbol=symbol, orderId=o['orderId'])
    except Exception as e:
        print(f"[CANCEL ERROR] {e}")

def enter(symbol, side):
    bal   = get_usdt_balance()
    price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    atr   = calc_indicators(fetch_klines(symbol,'1h'))['atr'].iloc[-1]
    tick  = float(next(f['tickSize'] for s in client.futures_exchange_info()['symbols'] if s['symbol']==symbol for f in s['filters'] if f['filterType']=='PRICE_FILTER'))
    min_diff = tick*5
    sl = min(price-atr, price-min_diff) if side=='LONG' else max(price+atr, price+min_diff)
    tp = max(price+atr*RR_RATIO, price+min_diff) if side=='LONG' else min(price-atr*RR_RATIO, price-min_diff)
    sl,tp = round(sl,2), round(tp,2)
    margin = bal*RISK_RATIO*0.95
    qty    = round(margin*LEVERAGE/price, 3)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    client.futures_create_order(symbol=symbol, side=SIDE_BUY if side=='LONG' else SIDE_SELL,
                                type=ORDER_TYPE_MARKET, quantity=qty)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="TAKE_PROFIT_MARKET", stopPrice=tp, closePosition=True)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="STOP_MARKET", stopPrice=sl, closePosition=True)
    now = datetime.now(timezone.utc)
    positions[symbol] = {'side':side,'entry_time':now,'qty':qty,'entry_price':price,'last_monitor':now}
    send_telegram(f"*ENTRY*\n{symbol} | {side}\nEntry: {float(price):.2f}\nTP: {float(tp):.2f} | SL: {float(sl):.2f}\nBalance: {float(bal):.2f} USDT")
    print(f"[ENTRY] {symbol} {side} at {price:.2f}")

def manage():
    now = datetime.now(timezone.utc)
    for sym,pos in list(positions.items()):
        df1 = calc_indicators(fetch_klines(sym,'1h'))
        if df1.empty: continue
        curr    = float(client.futures_symbol_ticker(symbol=sym)['price'])
        pnl     = (curr-pos['entry_price'])*pos['qty'] if pos['side']=='LONG' else (pos['entry_price']-curr)*pos['qty']
        pnl_pct = pnl/(pos['entry_price']*pos['qty'])*100
        if (now-pos['last_monitor']).total_seconds()>=MONITOR_TERMINAL_INTERVAL:
            print(f"[MONITOR] {sym} PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) age:{now-pos['entry_time']}")
            pos['last_monitor']=now
        if is_early_exit(df1,pos):
            cancel_tp_sl(sym)
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"*EARLY EXIT* {sym} | PnL:{float(pnl):+.2f} USDT ({float(pnl_pct):+.2f}%)")
            print(f"[EARLY EXIT] {sym}")
            positions.pop(sym)

def main_loop():
    while True:
        try:
            if len(positions) < MAX_POSITIONS:
                for sym in TRADE_SYMBOLS:
                    if sym in positions: continue
                    side = check_entry(sym)
                    if side:
                        enter(sym, side)
                        break
            manage()
            time.sleep(ANALYSIS_INTERVAL)
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)

if __name__ == '__main__':
    send_telegram("🤖 Bot started.")
    main_loop()
