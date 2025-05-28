import os
import time
import math
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance 클라이언트
client = Client(API_KEY, API_SECRET)

# 설정값
LEVERAGE = 10
BALANCE_USDT = 100
RISK_RATIO = 0.3
MAX_POSITIONS = 3
ANALYSIS_INTERVAL = 1             # 초 단위
REANALYSIS_INTERVAL = 60         # 5분봉 재분석 1분 주기
TELEGRAM_SUMMARY_INTERVAL = 1800  # 30분
MIN_ADX = 20
ATR_PERIOD = 14
OSC_PERIOD = 14
EMA_SHORT = 20
RSI_PERIOD = 14
RR_RATIO = 1.3
TIMEOUT1 = timedelta(hours=2, minutes=30)
TIMEOUT2 = timedelta(hours=3)

# 상태 저장
positions = {}  # {symbol: {side, entry_time, entry_price, qty}}
last_summary = datetime.now(timezone.utc) - timedelta(seconds=TELEGRAM_SUMMARY_INTERVAL)

# 유틸 함수
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def get_top_symbols():
    tickers = client.futures_ticker_24hr()
    df = pd.DataFrame(tickers)
    df['quoteVolume'] = df['quoteVolume'].astype(float)
    df = df[df['symbol'].str.endswith('USDT') & (df['contractType']=='PERPETUAL')]
    return df.nlargest(100, 'quoteVolume')['symbol'].tolist()

def fetch_klines(symbol, interval, limit=100):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    df[['o','h','l','c']] = df[['o','h','l','c']].astype(float)
    df['t'] = pd.to_datetime(df['t'], unit='ms')
    return df

def calc_indicators(df):
    df['rsi'] = RSIIndicator(df['c'], RSI_PERIOD).rsi()
    df['macd_diff'] = MACD(df['c']).macd_diff()
    df['ema'] = EMAIndicator(df['c'], EMA_SHORT).ema_indicator()
    df['adx'] = ADXIndicator(df['h'], df['l'], df['c'], window=RSI_PERIOD).adx()
    df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=OSC_PERIOD).stoch()
    df['atr'] = AverageTrueRange(df['h'], df['l'], df['c'], window=ATR_PERIOD).average_true_range()
    return df.dropna()

def round_price(symbol, price):
    info = client.futures_exchange_info()['symbols']
    for s in info:
        if s['symbol']==symbol:
            ts = float(next(f['tickSize'] for f in s['filters'] if f['filterType']=='PRICE_FILTER'))
            prec = int(-math.log(ts,10))
            return round(price, prec)
    return round(price,8)

def round_qty(symbol, qty):
    info = client.futures_exchange_info()['symbols']
    for s in info:
        if s['symbol']==symbol:
            ss = float(next(f['stepSize'] for f in s['filters'] if f['filterType']=='LOT_SIZE'))
            prec = int(-math.log(ss,10))
            return float(f"{qty:.{prec}f}")
    return qty

# 신호 판단
def check_entry(signal_df):
    last = signal_df.iloc[-1]
    if last['adx']<MIN_ADX: return False, None
    long_score = sum([last['rsi']<40, last['macd_diff']>0, last['c']>last['ema'], last['stoch']<20])
    short_score= sum([last['rsi']>60, last['macd_diff']<0, last['c']<last['ema'], last['stoch']>80])
    core_long = sum([last['macd_diff']>0, last['c']>last['ema'], last['adx']>MIN_ADX])
    core_short= sum([last['macd_diff']<0, last['c']<last['ema'], last['adx']>MIN_ADX])
    if core_long>=2 and long_score>=3: return True, 'LONG'
    if core_short>=2 and short_score>=3: return True, 'SHORT'
    return False, None

# 진입 함수
def enter(symbol, side):
    price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    df = calc_indicators(fetch_klines(symbol,'1h'))
    atr = df['atr'].iloc[-1]
    sl = price-atr if side=='LONG' else price+atr
    tp = price+atr*RR_RATIO if side=='LONG' else price-atr*RR_RATIO
    sl, tp = round_price(symbol,sl), round_price(symbol,tp)
    qty = BALANCE_USDT*RISK_RATIO*LEVERAGE/price
    qty = round_qty(symbol,qty)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    client.futures_create_order(symbol=symbol,side=SIDE_BUY if side=='LONG' else SIDE_SELL,type=ORDER_TYPE_MARKET,quantity=qty)
    client.futures_create_order(symbol=symbol,side=SIDE_SELL if side=='LONG' else SIDE_BUY,type="TAKE_PROFIT_MARKET",stopPrice=tp,closePosition=True)
    client.futures_create_order(symbol=symbol,side=SIDE_SELL if side=='LONG' else SIDE_BUY,type="STOP_MARKET",stopPrice=sl,closePosition=True)
    positions[symbol]={'side':side,'entry_price':price,'qty':qty,'entry_time':datetime.now(timezone.utc),'last_reanalysis':datetime.now(timezone.utc)}
    send_telegram(f"[ENTRY] {symbol} {side} @{price:.2f}, TP={tp}, SL={sl}")

# 관리 함수
def manage():
    now=datetime.now(timezone.utc)
    for sym,pos in list(positions.items()):
        age=now-pos['entry_time']
        df5=calc_indicators(fetch_klines(sym,'5m'))
        last=df5.iloc[-1]
        rev_score=sum([last['rsi']>50 if pos['side']=='LONG' else last['rsi']<50,
                       last['macd_diff']<0 if pos['side']=='LONG' else last['macd_diff']>0,
                       last['c']<last['ema'] if pos['side']=='LONG' else last['c']>last['ema'],
                       last['stoch']>50 if pos['side']=='LONG' else last['stoch']<50])
        if rev_score>=3:
            client.futures_create_order(symbol=sym,side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,type=ORDER_TYPE_MARKET,quantity=pos['qty'])
            send_telegram(f"[STRONG EXIT] {sym} rev={rev_score}")
            del positions[sym]; continue
        if age>=TIMEOUT2:
            client.futures_create_order(symbol=sym,side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,type=ORDER_TYPE_MARKET,quantity=pos['qty'])
            send_telegram(f"[TIME EXIT] {sym} 3h")
            del positions[sym]
        elif age>=TIMEOUT1 and (now-pos['last_reanalysis']).total_seconds()>=REANALYSIS_INTERVAL:
            entry=pos['entry_price']; curr=float(client.futures_mark_price(symbol=sym)['markPrice'])
            pnl=(curr-entry)*pos['qty'] if pos['side']=='LONG' else (entry-curr)*pos['qty']
            if pnl<=0:
                df1=calc_indicators(fetch_klines(sym,'1h')).iloc[-1]
                score=sum([df1['rsi']<40 if pos['side']=='LONG' else df1['rsi']>60,
                           df1['macd_diff']>0 if pos['side']=='LONG' else df1['macd_diff']<0,
                           df1['c']>df1['ema'] if pos['side']=='LONG' else df1['c']<df1['ema'],
                           df1['stoch']<20 if pos['side']=='LONG' else df1['stoch']>80])
                if score<3:
                    client.futures_create_order(symbol=sym,side=SIDE_SELL if pos['side']=='LONG' else SIDE_BUY,type=ORDER_TYPE_MARKET,quantity=pos['qty'])
                    send_telegram(f"[REEXIT] {sym} score={score}")
                    del positions[sym]
                else:
                    pos['last_reanalysis']=now

def summary():
    global last_summary
    now=datetime.now(timezone.utc)
    if (now-last_summary).total_seconds()>=TELEGRAM_SUMMARY_INTERVAL:
        msgs=[f"{s}:{positions[s]['side']}@{positions[s]['entry_price']:.2f} q={positions[s]['qty']}" for s in positions]
        send_telegram("[SUMMARY]\n"+"\n".join(msgs))
        last_summary=now

def main():
    while True:
        summary()
        top100=get_top_symbols()
        for sym in top100:
            if len(positions)<MAX_POSITIONS and sym not in positions:
                df1h=calc_indicators(fetch_klines(sym,'1h'))
                ok, side=check_entry(df1h)
                if ok:
                    enter(sym, side)
        manage()
        time.sleep(ANALYSIS_INTERVAL)

if __name__=='__main__': main()
