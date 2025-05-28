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
RISK_RATIO                = 0.3    # 30% of available balance
MAX_POSITIONS             = 3
ANALYSIS_INTERVAL         = 10     # seconds between analysis loops
MONITOR_INTERVAL          = 1      # seconds between monitoring loops
TELEGRAM_SUMMARY_INTERVAL = 1800   # seconds for summary & hold report
MONITOR_TERMINAL_INTERVAL = 30     # seconds for terminal monitor report
MIN_ADX                   = 20
ATR_PERIOD                = 14
OSC_PERIOD                = 14
EMA_SHORT                 = 9      # for short EMA in early exit
EMA_LONG                  = 21     # for long EMA in early exit
RSI_PERIOD                = 14
RR_RATIO                  = 1.3
TIMEOUT1                  = timedelta(hours=2, minutes=30)
TIMEOUT2                  = timedelta(hours=3)
EARLY_EXIT_PCT            = 0.01   # 1% for early exit

# State
positions    = {}  # symbol -> {side, entry_time, qty, entry_price, last_monitor}
last_summary = datetime.now(timezone.utc) - timedelta(seconds=TELEGRAM_SUMMARY_INTERVAL)

# Utility functions
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
    except:
        pass

def get_usdt_balance():
    bal = client.futures_account_balance()
    for entry in bal:
        if entry['asset'] == 'USDT':
            return float(entry['withdrawAvailable'])
    return 0.0

# Fetch valid symbols
def get_valid_futures_symbols():
    info = client.futures_exchange_info()
    return sorted([s['symbol'] for s in info['symbols'] if s['contractType']=='PERPETUAL' and s['quoteAsset']=='USDT'])

TRADE_SYMBOLS = get_valid_futures_symbols()

# Market data
def fetch_klines(symbol, interval, limit=100):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    df[['o','h','l','c']] = df[['o','h','l','c']].astype(float)
    df['t'] = pd.to_datetime(df['t'], unit='ms')
    df.set_index('t', inplace=True)
    return df

# Indicators including early-exit ones
def calc_indicators(df):
    min_needed = max(ATR_PERIOD, OSC_PERIOD, EMA_LONG, RSI_PERIOD)
    if df is None or len(df) < min_needed:
        return pd.DataFrame()
    df['rsi']      = RSIIndicator(df['c'], RSI_PERIOD).rsi()
    df['macd_diff']= MACD(df['c']).macd_diff()
    df['ema']      = EMAIndicator(df['c'], EMA_LONG).ema_indicator()
    df['adx']      = ADXIndicator(df['h'], df['l'], df['c'], window=RSI_PERIOD).adx()
    df['stoch']    = StochasticOscillator(df['h'], df['l'], df['c'], window=OSC_PERIOD).stoch()
    df['atr']      = AverageTrueRange(df['h'], df['l'], df['c'], window=ATR_PERIOD).average_true_range()
    # early-exit indicators
    df['cci']      = CCIIndicator(df['h'], df['l'], df['c'], window=OSC_PERIOD).cci()
    df['ema9']     = EMAIndicator(df['c'], EMA_SHORT).ema_indicator()
    df['ema21']    = EMAIndicator(df['c'], EMA_LONG).ema_indicator()
    df['stochrsi'] = StochRSIIndicator(df['c'], window=RSI_PERIOD).stochrsi()
    df['wpr']      = WilliamsRIndicator(df['h'], df['l'], df['c'], lbp=14).wr()
    return df.dropna()

# Rounding
def get_price_tick(symbol):
    for s in client.futures_exchange_info()['symbols']:
        if s['symbol']==symbol:
            return float(next(f['tickSize'] for f in s['filters'] if f['filterType']=='PRICE_FILTER'))
    return 0.01

def round_price(symbol, price):
    tick = get_price_tick(symbol)
    prec = int(-math.log(tick,10))
    return round(price, prec)

def round_qty(symbol, qty):
    for s in client.futures_exchange_info()['symbols']:
        if s['symbol']==symbol:
            step= float(next(f['stepSize'] for f in s['filters'] if f['filterType']=='LOT_SIZE'))
            prec= int(-math.log(step,10))
            return float(f"{qty:.{prec}f}")
    return qty

# Entry logic unchanged
def check_entry(symbol):
    df = fetch_klines(symbol, '1h')
    if df.empty: return None
    df = calc_indicators(df)
    if df.empty: return None
    last = df.iloc[-1]
    if last['adx'] < MIN_ADX: return None
    long_score  = sum([last['rsi']<40, last['macd_diff']>0, last['c']>last['ema'], last['stoch']<20])
    short_score = sum([last['rsi']>60, last['macd_diff']<0, last['c']<last['ema'], last['stoch']>80])
    core_long   = sum([last['macd_diff']>0, last['c']>last['ema'], last['adx']>MIN_ADX])
    core_short  = sum([last['macd_diff']<0, last['c']<last['ema'], last['adx']>MIN_ADX])
    if core_long>=2 and long_score>=3: return 'LONG'
    if core_short>=2 and short_score>=3: return 'SHORT'
    return None

# Early exit condition
def is_early_exit(df, pos):
    last = df.iloc[-1]
    pnl_pct = (last['c']-pos['entry_price'])/pos['entry_price']*100 if pos['side']=='LONG' else (pos['entry_price']-last['c'])/pos['entry_price']*100
    # profit >= 1%
    if pnl_pct < EARLY_EXIT_PCT*100: return False
    # LONG: CCI < 100 or ema9 < ema21 or wpr > -20
    if pos['side']=='LONG' and (last['cci']<100 or last['ema9']<last['ema21'] or last['wpr']>-20):
        return True
    # SHORT: CCI > -100 or ema9 > ema21 or wpr < -80
    if pos['side']=='SHORT' and (last['cci']>-100 or last['ema9']>last['ema21'] or last['wpr']< -80):
        return True
    return False

# Enter trade and reporting
def enter(symbol, side):
    balance = get_usdt_balance()
    price   = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    atr     = calc_indicators(fetch_klines(symbol, '1h'))['atr'].iloc[-1]
    tick    = get_price_tick(symbol)
    min_diff= tick*5
    if side=='LONG':
        sl = min(price-atr, price-min_diff)
        tp = max(price+atr*RR_RATIO, price+min_diff)
    else:
        sl = max(price+atr, price+min_diff)
        tp = min(price-atr*RR_RATIO, price-min_diff)
    sl, tp = round_price(symbol, sl), round_price(symbol, tp)
    margin = balance * RISK_RATIO * 0.95
    qty    = round_qty(symbol, margin * LEVERAGE / price)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    client.futures_create_order(symbol=symbol, side=SIDE_BUY if side=='LONG' else SIDE_SELL,
                                type=ORDER_TYPE_MARKET, quantity=qty)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="TAKE_PROFIT_MARKET", stopPrice=tp, closePosition=True)
    client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="STOP_MARKET", stopPrice=sl, closePosition=True)
    now = datetime.now(timezone.utc)
    positions[symbol] = {'side': side, 'entry_time': now, 'qty': qty,
                         'entry_price': price, 'last_monitor': now}
    send_telegram(f"*ENTRY*\n{symbol} | {side}\nEntry: {price:.2f}\nTP: {tp:.2f} | SL: {sl:.2f}\nBalance: {balance:.2f} USDT")
    print(f"[ENTRY] {symbol} {side} at {price:.2f} qty={qty}")

# Manage positions with early exit integrated
def manage():
    now = datetime.now(timezone.utc)
    for sym, pos in list(positions.items()):
        df1h = calc_indicators(fetch_klines(sym, '1h'))
        df5m = calc_indicators(fetch_klines(sym, '5m'))
        if df1h.empty or df5m.empty:
            continue
        entry_price = pos['entry_price']
        curr = float(client.futures_symbol_ticker(symbol=sym)['price'])
        pnl = (curr-entry_price)*pos['qty'] if pos['side']=='LONG' else (entry_price-curr)*pos['qty']
        pnl_pct = pnl/(entry_price*pos['qty'])*100
        # terminal monitor
        if (now-pos['last_monitor']).total_seconds()>=MONITOR_TERMINAL_INTERVAL:
            print(f"[MONITOR] {sym} PnL:{pnl:+.2f} ({pnl_pct:+.2f}%) age:{now-pos['entry_time']}")
            pos['last_monitor'] = now
        # early exit
        if is_early_exit(df1h, pos):
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"*EARLY EXIT* {sym} | PnL:{pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
            print(f"[EARLY EXIT] {sym} pnl={pnl:.2f}")
            positions.pop(sym)
            continue
        # existing exit logic
        age = now - pos['entry_time']
        # strong reversal exit
        rev = sum([
            df5m.iloc[-1]['rsi']>50 if pos['side']=='LONG' else df5m.iloc[-1]['rsi']<50,
            df5m.iloc[-1]['macd_diff']<0 if pos['side']=='LONG' else df5m.iloc[-1]['macd_diff']>0,
            df5m.iloc[-1]['c']<df5m.iloc[-1]['ema'] if pos['side']=='LONG' else df5m.iloc[-1]['c']>df5m.iloc[-1]['ema'],
            df5m.iloc[-1]['stoch']>50 if pos['side']=='LONG' else df5m.iloc[-1]['stoch']<50
        ])
        if rev>=3:
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"*STRONG EXIT* {sym} | PnL:{pnl:+.2f} ({pnl_pct:+.2f}%)")
            print(f"[STRONG EXIT] {sym} rev={rev}")
            positions.pop(sym)
            continue
        # timeout or profit exit
        if age>=TIMEOUT2 or (age>=TIMEOUT1 and pnl>0):
            exit_type = 'TIME EXIT' if age>=TIMEOUT2 else 'PROFIT EXIT'
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"*{exit_type}* {sym} | PnL:{pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
            print(f"[{exit_type}] {sym}")
            positions.pop(sym)
        elif age>=TIMEOUT1:
            # re-exit logic unchanged
            score = sum([
                df1h.iloc[-1]['rsi']<40 if pos['side']=='LONG' else df1h.iloc[-1]['rsi']>60,
                df1h.iloc[-1]['macd_diff']>0 if pos['side']=='LONG' else df1h.iloc[-1]['macd_diff']<0,
                df1h.iloc[-1]['c']>df1h.iloc[-1]['ema'] if pos['side']=='LONG' else df1h.iloc[-1]['c']<df1h.iloc[-1]['ema'],
                df1h.iloc[-1]['stoch']<20 if pos['side']=='LONG' else df1h.iloc[-1]['stoch']>80
            ])
            client.futures_create_order(symbol=sym, side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET, quantity=pos['qty'])
            send_telegram(f"*REEXIT* {sym} | PnL:{pnl:+.2f} USDT ({pnl_pct:+.2f}%) | score={score}")
            print(f"[REEXIT] {sym} score={score}")
            positions.pop(sym)

# Summary & hold status report
def summary_and_hold_report():
    global last_summary
    now = datetime.now(timezone.utc)
    if (now-last_summary).total_seconds() >= TELEGRAM_SUMMARY_INTERVAL:
        msgs = []
        for s, pos in positions.items():
            curr = float(client.futures_symbol_ticker(symbol=s)['price'])
            pnl = (curr-pos['entry_price'])*pos['qty'] if pos['side']=='LONG' else (pos['entry_price']-curr)*pos['qty']
            pct = pnl/(pos['entry_price']*pos['qty'])*100
            msgs.append(f"{s} | {pos['side']} | PnL: {pnl:+.2f} USDT ({pct:+.2f}%)")
        send_telegram("*SUMMARY & HOLD STATUS*\n" + "\n".join(msgs))
        last_summary = now

# Main loop
def main():
    print("[BOT STARTED] Auto-trading bot is now running...")
    send_telegram("*BOT STARTED*\nAuto-trading bot is now running...")
    while True:
        # analysis phase
        print(f"[ANALYSIS] Checking {len(TRADE_SYMBOLS)} symbols | Time: {datetime.now(timezone.utc)}")
        for symbol in TRADE_SYMBOLS:
            if len(positions) < MAX_POSITIONS and symbol not in positions:
                side = check_entry(symbol)
                if side:
                    enter(symbol, side)
        summary_and_hold_report()
        # monitoring phase
        monitor_start = datetime.now(timezone.utc)
        while positions and (datetime.now(timezone.utc)-monitor_start).total_seconds() < ANALYSIS_INTERVAL:
            manage()
            time.sleep(MONITOR_INTERVAL)
        time.sleep(ANALYSIS_INTERVAL)

if __name__ == '__main__':
    main()
