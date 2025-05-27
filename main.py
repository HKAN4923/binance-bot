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
RR_RATIO = 1.3           # 리스크-리워드 비율 1:1.3
LEVERAGE = 10
SLEEP_INTERVAL = 10      # 10초 대기
MAX_CONCURRENT = 1       # 동시 1포지션

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance client 생성
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

# 심볼 리스트 (25개)
symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT",
    "XRPUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT",
    "LINKUSDT","UNIUSDT","BCHUSDT","ETCUSDT","XLMUSDT",
    "AAVEUSDT","MKRUSDT","COMPUSDT","SUSHIUSDT","AVAXUSDT",
    "FILUSDT","ATOMUSDT","EOSUSDT","THETAUSDT","TRXUSDT"
]

current_positions = 0
positions_lock = threading.Lock()

# 데이터 프레임 로드 및 지표 계산
def get_df(symbol, interval):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=100)
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
    for col in ["o","h","l","c"]:
        df[col] = df[col].astype(float)
    df['rsi']   = RSIIndicator(df['c'], window=14).rsi()
    df['macd']  = MACD(df['c']).macd_diff()
    df['ema9']  = EMAIndicator(df['c'], window=9).ema_indicator()
    df['adx']   = ADXIndicator(df['h'], df['l'], df['c'], window=14).adx()
    df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=14).stoch()
    return df

# 진입 신호 판단 (기준 완화)
def check_signal(df):
    last = df.iloc[-1]
    if last['adx'] < 10:
        return None
    if last['rsi'] < 42 and last['macd'] > 0 and last['c'] > last['ema9'] and last['stoch'] < 50:
        return 'LONG'
    if last['rsi'] > 58 and last['macd'] < 0 and last['c'] < last['ema9'] and last['stoch'] > 50:
        return 'SHORT'
    return None

# 잔고 조회
def get_balance():
    for b in client.futures_account_balance():
        if b['asset'] == 'USDT':
            return float(b['balance'])
    return 0.0

# 주문 수량 계산 (high:80%, low:20%)
def calc_qty(price, confidence):
    bal = get_balance()
    alloc = bal * (0.8 if confidence == 'high' else 0.2)
    return round(alloc / price, 6)

# 반대 방향 시그널 확인 후 탈출 판단
def opposite_signal(df, current_side):
    signal = check_signal(df)
    return (current_side == 'LONG' and signal == 'SHORT') or (current_side == 'SHORT' and signal == 'LONG')

# 시장가 진입 및 TP/SL 설정
def execute_trade(symbol, side, price, confidence):
    global current_positions
    qty = calc_qty(price, confidence)
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
    client.futures_create_order(symbol=symbol, side=order_side, type=ORDER_TYPE_MARKET, quantity=qty)

    sl_price = price * (0.98 if side == 'LONG' else 1.02)
    rr_dist = abs(price - sl_price) * RR_RATIO
    tp_price = price + rr_dist if side == 'LONG' else price - rr_dist

    client.futures_create_order(symbol=symbol,
                                side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="TAKE_PROFIT_MARKET",
                                stopPrice=round(tp_price,2), closePosition=True)
    client.futures_create_order(symbol=symbol,
                                side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                type="STOP_MARKET",
                                stopPrice=round(sl_price,2), closePosition=True)

    msg = f"{symbol} {side} 진입 @{price:.2f} | TP:{tp_price:.2f}, SL:{sl_price:.2f} ({confidence})"
    send_telegram(msg)
    log(msg)
    with positions_lock:
        current_positions += 1

    # 반대 시그널 확인 루프
    while True:
        df_check = get_df(symbol, '30m')
        if opposite_signal(df_check, side):
            client.futures_create_order(symbol=symbol,
                                        side=SIDE_SELL if side=='LONG' else SIDE_BUY,
                                        type=ORDER_TYPE_MARKET,
                                        quantity=qty)
            msg = f"{symbol} 반대 시그널 발생으로 청산"
            send_telegram(msg)
            log(msg)
            with positions_lock:
                current_positions -= 1
            break
        time.sleep(1)

# 메인 실행
if __name__ == '__main__':
    print("🔮 Bot started (완화된 기준, 25개 심볼, 반대시그널 탈출 포함)")
    send_telegram("🤖 Bot started: 30m/1h 신호 기반")

    while True:
        print(f"[{datetime.now():%H:%M:%S}] 새 사이클 시작...")
        for symbol in symbols:
            with positions_lock:
                if current_positions >= MAX_CONCURRENT:
                    break
            df_30m = get_df(symbol, '30m')
            df_1h  = get_df(symbol, '1h')
            sig30  = check_signal(df_30m)
            sig1h  = check_signal(df_1h)
            price  = float(client.futures_mark_price(symbol=symbol)['markPrice'])

            if sig30 and sig30 == sig1h:
                execute_trade(symbol, sig30, price, 'high')
                break
            elif sig30 and not sig1h:
                execute_trade(symbol, sig30, price, 'low')
                break
            elif sig1h and not sig30:
                execute_trade(symbol, sig1h, price, 'low')
                break

        time.sleep(SLEEP_INTERVAL)
