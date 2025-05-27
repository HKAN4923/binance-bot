import os
import time
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
import requests
import logging

# 설정값
RR_RATIO = 1.3           # 리스크-리워드 비율 1:1.3 (보수적)
LEVERAGE = 10
SLEEP_INTERVAL = 10
MAX_CONCURRENT = 1

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance client
client = Client(API_KEY, API_SECRET)

# 로깅
logging.basicConfig(filename='trade_log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')
def log(msg):
    print(msg)
    logging.info(msg)

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# 심볼 리스트
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

current_positions = 0
positions_lock = threading.Lock()

def get_df(symbol, interval):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=100)
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    for col in ["o", "h", "l", "c"]:
        df[col] = df[col].astype(float)
    df['rsi'] = RSIIndicator(df['c'], window=14).rsi()
    df['macd'] = MACD(df['c']).macd_diff()
    df['ema9'] = EMAIndicator(df['c'], window=9).ema_indicator()
    df['ema21'] = EMAIndicator(df['c'], window=21).ema_indicator()
    df['adx'] = ADXIndicator(df['h'], df['l'], df['c'], window=14).adx()
    df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=14).stoch()
    return df

def check_signal(df):
    last = df.iloc[-1]
    if last['adx'] < 15:
        return None
    if last['rsi'] < 35 and last['macd'] > 0 and last['c'] > last['ema9'] and last['stoch'] < 30:
        return 'LONG'
    if last['rsi'] > 65 and last['macd'] < 0 and last['c'] < last['ema9'] and last['stoch'] > 70:
        return 'SHORT'
    return None

def get_balance():
    for b in client.futures_account_balance():
        if b['asset'] == 'USDT':
            return float(b['balance'])
    return 0.0

def calc_qty(price, confidence):
    bal = get_balance()
    risk_amt = bal * (0.2 if confidence == 'low' else 0.8)
    return round(risk_amt / price, 3)

def execute_trade(symbol, side, price, confidence):
    global current_positions
    qty = calc_qty(price, confidence)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
    client.futures_create_order(symbol=symbol, side=order_side, type=ORDER_TYPE_MARKET, quantity=qty)

    # 손절 2%, 리스크리워드 1:1.2
    sl_price = price * 0.98 if side == 'LONG' else price * 1.02
    tp_price = price + (abs(price - sl_price) * RR_RATIO) if side == 'LONG' else price - (abs(price - sl_price) * RR_RATIO)

    client.futures_create_order(
        symbol=symbol,
        side=SIDE_SELL if side == 'LONG' else SIDE_BUY,
        type="TAKE_PROFIT_MARKET",
        stopPrice=round(tp_price, 2),
        closePosition=True
    )
    client.futures_create_order(
        symbol=symbol,
        side=SIDE_SELL if side == 'LONG' else SIDE_BUY,
        type="STOP_MARKET",
        stopPrice=round(sl_price, 2),
        closePosition=True
    )

    msg = f"✅ {symbol} {side} 진입! 진입가: {price:.2f}, 익절: {tp_price:.2f}, 손절: {sl_price:.2f} ({confidence})"
    send_telegram(msg)
    log(msg)
    with positions_lock:
        current_positions += 1

def main():
    print("🔮 Bot started (entry by 30m or 1h signal) ...")
    send_telegram("🤖 Binance bot 시작됨 (30분 또는 1시간 시그널 기반)")
    while True:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] === 새 사이클 ===")
        for symbol in symbols:
            with positions_lock:
                if current_positions >= MAX_CONCURRENT:
                    break
            try:
                df_30m = get_df(symbol, '30m')
                df_1h  = get_df(symbol, '1h')
                sig_30m = check_signal(df_30m)
                sig_1h  = check_signal(df_1h)
                price = float(client.futures_mark_price(symbol)['markPrice'])

                if sig_30m and sig_1h and sig_30m == sig_1h:
                    execute_trade(symbol, sig_30m, price, confidence='high')
                elif sig_30m and not sig_1h:
                    execute_trade(symbol, sig_30m, price, confidence='low')
                elif sig_1h and not sig_30m:
                    execute_trade(symbol, sig_1h, price, confidence='low')

            except Exception as e:
                log(f"Error: {symbol}: {e}")
                send_telegram(f"⚠️ {symbol} 오류: {e}")
        time.sleep(SLEEP_INTERVAL)

if __name__ == '__main__':
    main()
