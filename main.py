import os
import time
import math
import threading
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
import requests
import logging

# 1) 환경 변수 로드
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path)

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not API_KEY or not API_SECRET:
    raise SystemExit('Error: BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env')

client = Client(API_KEY, API_SECRET)

# 2) 설정값
RR_RATIO = 1.3
LEVERAGE = 10
SLEEP_INTERVAL = 10
MAX_CONCURRENT = 1

# 3) 로깅 및 텔레그램
logging.basicConfig(filename='trade_log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

def log(msg):
    print(msg)
    logging.info(msg)

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")

# 4) 심볼 리스트 및 필터링
raw_symbols = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT"]

def get_valid_symbols(symbols):
    try:
        info = client.futures_exchange_info()
        valid = {s['symbol'] for s in info['symbols'] if s['contractType'] == 'PERPETUAL'}
        return [s for s in symbols if s in valid]
    except Exception as e:
        log(f"Error fetching exchange info: {e}")
        return []

symbols = get_valid_symbols(raw_symbols)
if not symbols:
    raise SystemExit('No valid futures symbols found.')

current_positions = 0
positions_lock = threading.Lock()

# 5) 지표 계산용 데이터 가져오기
def get_df(symbol, interval):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=100)
        df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbb","tbq","i"])
        df = df.astype({"o":float, "h":float, "l":float, "c":float})
        df['rsi'] = RSIIndicator(df['c'], window=14).rsi()
        df['macd'] = MACD(df['c']).macd_diff()
        df['ema9'] = EMAIndicator(df['c'], window=9).ema_indicator()
        df['adx'] = ADXIndicator(df['h'], df['l'], df['c'], window=14).adx()
        df['stoch'] = StochasticOscillator(df['h'], df['l'], df['c'], window=14).stoch()
        return df
    except Exception as e:
        log(f"get_df error for {symbol}: {e}")
        return None

# 6) 신호 판단
def check_signal(df):
    last = df.iloc[-1]
    if last['adx'] < 10:
        return None
    if last['rsi'] < 42 and last['macd'] > 0 and last['c'] > last['ema9'] and last['stoch'] < 50:
        return 'LONG'
    if last['rsi'] > 58 and last['macd'] < 0 and last['c'] < last['ema9'] and last['stoch'] > 50:
        return 'SHORT'
    return None

# 7) 심볼별 수량 자릿수 맞추기
def get_step_size(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    return float(f['stepSize'])
    return 0.001

def round_step_size(qty, step_size):
    return math.floor(qty / step_size) * step_size

# 8) 잔고 및 수량 계산
def get_balance():
    try:
        for b in client.futures_account_balance():
            if b['asset'] == 'USDT':
                return float(b['balance'])
    except Exception as e:
        log(f"get_balance error: {e}")
    return 0.0

def calc_qty(price, confidence, symbol):
    bal = get_balance()
    alloc = bal * (0.3 if confidence == 'high' else 0.1)
    raw_qty = alloc / price
    step = get_step_size(symbol)
    return round_step_size(raw_qty, step)

# 9) 반대 시그널 판단
def opposite_signal(df, side):
    sig = check_signal(df)
    return (side == 'LONG' and sig == 'SHORT') or (side == 'SHORT' and sig == 'LONG')

# 10) 거래 실행
def execute_trade(symbol, side, price, confidence):
    global current_positions
    qty = calc_qty(price, confidence, symbol)
    if qty <= 0: return

    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
    side_order = SIDE_BUY if side == 'LONG' else SIDE_SELL
    client.futures_create_order(symbol=symbol, side=side_order, type=ORDER_TYPE_MARKET, quantity=qty)

    sl = price * (0.98 if side == 'LONG' else 1.02)
    rr_dist = abs(price - sl) * RR_RATIO
    tp = price + rr_dist if side == 'LONG' else price - rr_dist

    exit_side = SIDE_SELL if side == 'LONG' else SIDE_BUY
    client.futures_create_order(symbol=symbol, side=exit_side, type='TAKE_PROFIT_MARKET', stopPrice=round(tp, 2), closePosition=True)
    client.futures_create_order(symbol=symbol, side=exit_side, type='STOP_MARKET', stopPrice=round(sl, 2), closePosition=True)

    msg = f"{symbol} {side}@{price:.2f} TP:{tp:.2f} SL:{sl:.2f} ({confidence})"
    send_telegram(msg)
    log(msg)

    with positions_lock:
        current_positions += 1

    while True:
        df_chk = get_df(symbol, '30m')
        if df_chk is not None and not df_chk.empty and opposite_signal(df_chk, side):
            client.futures_create_order(symbol=symbol, side=exit_side, type=ORDER_TYPE_MARKET, quantity=qty)
            msg2 = f"{symbol} 반대신호 청산"
            send_telegram(msg2)
            log(msg2)
            with positions_lock:
                current_positions -= 1
            break
        time.sleep(1)

# 11) 워커 및 메인

def trade_worker(symbol):
    df30 = get_df(symbol, '30m')
    df1h = get_df(symbol, '1h')
    if df30 is None or df30.empty or df1h is None or df1h.empty:
        return

    sig30 = check_signal(df30)
    sig1h = check_signal(df1h)

    try:
        price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    except Exception as e:
        log(f"mark_price error for {symbol}: {e}")
        return

    with positions_lock:
        if current_positions >= MAX_CONCURRENT:
            return

    if sig30 and sig30 == sig1h:
        execute_trade(symbol, sig30, price, 'high')
    elif sig30 and not sig1h:
        execute_trade(symbol, sig30, price, 'low')
    elif sig1h and not sig30:
        execute_trade(symbol, sig1h, price, 'low')

def main():
    print("🔮 Bot started (Precision 대응 포함)")
    send_telegram("🤖 Bot started")
    while True:
        print(f"[{datetime.now():%H:%M:%S}] Cycle start...")
        threads = []
        for sym in symbols:
            t = threading.Thread(target=trade_worker, args=(sym,))
            threads.append(t)
            t.start()
            time.sleep(1)
        for t in threads:
            t.join()
        time.sleep(SLEEP_INTERVAL)

if __name__ == '__ma