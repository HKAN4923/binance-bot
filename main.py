import os
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
import requests
import logging

# 로그 설정
logging.basicConfig(filename='trade_log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

def log(msg):
    print(msg)
    logging.info(msg)

# 환경 변수 로드
load_dotenv()
API_KEY          = os.getenv("BINANCE_API_KEY")
API_SECRET       = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 바이낸스 클라이언트
client = Client(API_KEY, API_SECRET)

# 심볼 리스트 (30개)
symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT","XRPUSDT",
    "DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT","LINKUSDT","UNIUSDT",
    "BCHUSDT","ETCUSDT","XLMUSDT","AAVEUSDT","MKRUSDT","COMPUSDT",
    "SUSHIUSDT","AVAXUSDT","FILUSDT","ATOMUSDT","EOSUSDT","THETAUSDT",
    "TRXUSDT","NEARUSDT","ALGOUSDT","FTMUSDT","KSMUSDT","XTZUSDT"
]

# 설정 값
LEVERAGE         = 10
FORCE_HOURS      = 4
SLEEP_INTERVAL   = 10    # 대기시간 10초
MAX_CONCURRENT   = 1     # 포지션 1개 제한

current_positions = 0
positions_lock    = threading.Lock()

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_df(sym):
    data = client.futures_klines(symbol=sym, interval="5m", limit=100)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    for col in ["o","h","l","c"]:
        df[col] = df[col].astype(float)
    df['rsi']   = RSIIndicator(df['c'], window=14).rsi()
    df['macd']  = MACD(df['c']).macd_diff()
    df['ema9']  = EMAIndicator(df['c'], window=9).ema_indicator()
    df['ema21'] = EMAIndicator(df['c'], window=21).ema_indicator()
    df['adx']   = ADXIndicator(df['h'], df['l'], df['c'], window=14).adx()
    df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=14).stoch()
    df['swing_high'] = df['h'].rolling(20).max()
    df['swing_low']  = df['l'].rolling(20).min()
    return df

def check_signal(df):
    last = df.iloc[-1]
    if last['adx'] < 20:
        return None
    if last['rsi'] < 30 and last['macd'] > 0 and last['c'] > last['ema9'] and last['stoch'] < 20:
        return 'LONG'
    if last['rsi'] > 70 and last['macd'] < 0 and last['c'] < last['ema9'] and last['stoch'] > 80:
        return 'SHORT'
    return None

def get_balance():
    for b in client.futures_account_balance():
        if b['asset']=='USDT':
            return float(b['balance'])
    return 0.0

def calc_qty(price, risk_pct=0.2):
    bal = get_balance()
    risk_amt = bal * risk_pct
    return round(risk_amt / price, 6)

def execute_trade(sym, side, df):
    global current_positions
    client.futures_change_leverage(symbol=sym, leverage=LEVERAGE)
    price = float(client.futures_mark_price(sym)['markPrice'])
    qty   = calc_qty(price)
    order_side = SIDE_BUY if side=='LONG' else SIDE_SELL
    client.futures_create_order(symbol=sym, side=order_side, type=ORDER_TYPE_MARKET, quantity=qty)
    last = df.iloc[-1]
    if side=='LONG':
        tp, sl = last['swing_high'], last['swing_low']
    else:
        tp, sl = last['swing_low'], last['swing_high']
    tp = min(max(tp, price*1.01), price*1.05)
    sl = max(min(sl, price*0.99), price*0.95)
    client.futures_create_order(symbol=sym,
                                side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="TAKE_PROFIT_MARKET", stopPrice=round(tp,2), closePosition=True)
    client.futures_create_order(symbol=sym,
                                side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="STOP_MARKET", stopPrice=round(sl,2), closePosition=True)
    msg = f"{sym} {side} @ {price:.2f}  TP:{tp:.2f}, SL:{sl:.2f}"
    send_telegram(msg)
    log(msg)
    with positions_lock:
        current_positions += 1
    return price, qty, side

def monitor_position(sym, entry_price, qty, side):
    global current_positions
    start = datetime.now()
    max_hold = timedelta(hours=FORCE_HOURS)
    try:
        while True:
            time.sleep(30)
            price = float(client.futures_mark_price(sym)['markPrice'])
            df = get_df(sym)
            new_sig = check_signal(df)
            if df['adx'].iloc[-1] < 15:
                client.futures_create_order(symbol=sym,
                                            side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                            type=ORDER_TYPE_MARKET, quantity=qty/2)
                send_telegram(f"Sideway exit 50% {sym} @ {price:.2f}")
                log(f"Sideway exit 50% {sym} @ {price:.2f}")
                break
            if datetime.now() - start > max_hold and new_sig != side:
                client.futures_create_order(symbol=sym,
                                            side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                            type=ORDER_TYPE_MARKET, quantity=qty)
                send_telegram(f"Force close {sym} @ {price:.2f}")
                log(f"Force close {sym} @ {price:.2f}")
                break
    finally:
        with positions_lock:
            current_positions -= 1

# 메인 루프
if __name__=='__main__':
    print("🔮 Bot is running…")
    send_telegram("🔮 Bot started (1 position max, 10s interval)")
    total_wait = 0
    while True:
        print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] === 새 사이클 시작 ===")
        for sym in symbols:
            with positions_lock:
                pos = current_positions
            if pos >= MAX_CONCURRENT:
                continue
            try:
                df = get_df(sym)
                sig = check_signal(df)
                if sig:
                    entry, qty, side = execute_trade(sym, sig, df)
                    threading.Thread(target=monitor_position, args=(sym, entry, qty, side), daemon=True).start()
                    break  # 1포지션만 허용
            except Exception as e:
                send_telegram(f"Error {sym}: {e}")
                log(f"Error {sym}: {e}")
        total_wait += SLEEP_INTERVAL
        print(f"[{datetime.now():%H:%M:%S}] 사이클 완료, 10초 대기... (누적 대기: {total_wait}s)")
        time.sleep(SLEEP_INTERVAL)
