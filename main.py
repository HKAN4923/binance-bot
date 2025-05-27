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

# ✅ 절대경로로 .env 로드
load_dotenv(dotenv_path="/home/hgymire3123/binance-bot/.env")

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)

# 로깅 설정
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

# ✅ 심볼 리스트 (100개)
symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT","XRPUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
    "LINKUSDT","UNIUSDT","BCHUSDT","ETCUSDT","XLMUSDT","AAVEUSDT","MKRUSDT","COMPUSDT","SUSHIUSDT","AVAXUSDT",
    "FILUSDT","ATOMUSDT","EOSUSDT","THETAUSDT","TRXUSDT","NEARUSDT","ARBUSDT","OPUSDT","IMXUSDT","GMXUSDT",
    "DYDXUSDT","APEUSDT","SANDUSDT","MANAUSDT","RNDRUSDT","FTMUSDT","GALAUSDT","RLCUSDT","CRVUSDT","ENSUSDT",
    "CFXUSDT","KLAYUSDT","ZILUSDT","1INCHUSDT","ALGOUSDT","ANKRUSDT","CHZUSDT","TOMOUSDT","OCEANUSDT","FLUXUSDT",
    "COTIUSDT","BELUSDT","BATUSDT","DENTUSDT","RUNEUSDT","LINAUSDT","ICXUSDT","STMXUSDT","QTUMUSDT","ZRXUSDT",
    "BLZUSDT","STORJUSDT","KAVAUSDT","INJUSDT","TLMUSDT","VETUSDT","WAVESUSDT","IOSTUSDT","MTLUSDT","TRBUSDT",
    "FETUSDT","HOOKUSDT","IDUSDT","PHBUSDT","JOEUSDT","BICOUSDT","ASTRUSDT","LDOUSDT","PEOPLEUSDT","XEMUSDT",
    "ALPHAUSDT","NKNUSDT","SLPUSDT","SYSUSDT","HIGHUSDT","DGBUSDT","BANDUSDT","NMRUSDT","GLMRUSDT","MOVRUSDT",
    "CKBUSDT","API3USDT","HIFIUSDT","RIFUSDT","ERNUSDT","XNOUSDT","MDTUSDT","SPELLUSDT","TUSDT","PYRUSDT"
]

def get_klines(symbol, interval, limit):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','close_time','quote_asset_volume','num_trades','taker_buy_base','taker_buy_quote','ignore'])
        df['close'] = df['close'].astype(float)
        return df
    except Exception as e:
        log(f"Error fetching {symbol} - {e}")
        return None

def analyze_symbol(symbol):
    df = get_klines(symbol, '15m', 100)
    if df is None:
        return None, 0.0
    close = df['close']

    ema = EMAIndicator(close, window=20).ema_indicator()
    rsi = RSIIndicator(close, window=14).rsi()
    stoch = StochasticOscillator(df['high'].astype(float), df['low'].astype(float), close, window=14).stoch()
    macd = MACD(close).macd_diff()
    adx = ADXIndicator(df['high'].astype(float), df['low'].astype(float), close, window=14).adx()

    signal = None
    confidence = 0

    if close.iloc[-1] > ema.iloc[-1] and rsi.iloc[-1] > 50 and macd.iloc[-1] > 0 and adx.iloc[-1] > 25:
        signal = 'long'
        confidence = (rsi.iloc[-1] - 50) / 50
    elif close.iloc[-1] < ema.iloc[-1] and rsi.iloc[-1] < 50 and macd.iloc[-1] < 0 and adx.iloc[-1] > 25:
        signal = 'short'
        confidence = (50 - rsi.iloc[-1]) / 50

    return signal, round(confidence, 2)

def get_balance():
    for b in client.futures_account_balance():
        if b['asset'] == 'USDT':
            return float(b['balance'])
    return 0

def calc_qty(price, confidence):
    bal = get_balance()
    risk = bal * 0.3  # 30% 고정 리스크
    return round((risk / price) * confidence, 3)

def execute_trade(symbol, signal, price, position):
    qty = calc_qty(price, confidence=1.0)  # 자동 진입 기준 confidence 1.0으로 가정
    if qty <= 0:
        return

    side = SIDE_BUY if signal == 'long' else SIDE_SELL
    client.futures_create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=qty)

    entry = price
    stop = entry * (0.97 if signal == 'long' else 1.03)
    target = entry * (1.06 if signal == 'long' else 0.94)

    sl_side = SIDE_SELL if signal == 'long' else SIDE_BUY
    tp_side = SIDE_SELL if signal == 'long' else SIDE_BUY

    client.futures_create_order(symbol=symbol, side=tp_side, type='TAKE_PROFIT_MARKET', stopPrice=target, quantity=qty, timeInForce='GTC')
    client.futures_create_order(symbol=symbol, side=sl_side, type='STOP_MARKET', stopPrice=stop, quantity=qty, timeInForce='GTC')

    msg = f"[{symbol}] {signal.upper()} 진입\n수량: {qty}\n진입가: {entry}\n익절가: {target}\n손절가: {stop}"
    log(msg)
    send_telegram(msg)

def trade_worker(symbol):
    signal, confidence = analyze_symbol(symbol)
    if signal and confidence > 0.4:
        price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
        execute_trade(symbol, signal, price, 'low')

def main():
    while True:
        threads = []
        for symbol in symbols:
            t = threading.Thread(target=trade_worker, args=(symbol,))
            threads.append(t)
            t.start()
            time.sleep(1)

        for t in threads:
            t.join()

        time.sleep(300)  # 5분 대기 후 반복

if __name__ == "__main__":
    main()
