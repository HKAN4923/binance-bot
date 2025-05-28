# my_binance_bot.py

import time
import math
import pytz
import ccxt
import requests
import threading
import numpy as np
import talib
from datetime import datetime, timedelta

# ========= 사용자 설정 =========
API_KEY = 'YOUR_BINANCE_API_KEY'
API_SECRET = 'YOUR_BINANCE_SECRET'
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
TELEGRAM_CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'
# ===============================

binance = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})
binance.set_sandbox_mode(False)

open_positions = {}
trade_history = []  # 각 거래: {'symbol','profit','time'}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def get_ohlcv(symbol, timeframe='1h', limit=100):
    return binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

def calculate_indicators(data):
    closes = np.array([x[4] for x in data])
    highs  = np.array([x[2] for x in data])
    lows   = np.array([x[3] for x in data])
    return {
        'rsi': talib.RSI(closes, timeperiod=14)[-1],
        'macd': talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)[0][-1],
        'macd_signal': talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)[1][-1],
        'stoch_k': talib.STOCH(highs, lows, closes)[0][-1],
        'adx': talib.ADX(highs, lows, closes)[-1]
    }

def get_signal(symbol):
    data_1h = get_ohlcv(symbol, '1h')
    data_4h = get_ohlcv(symbol, '4h')

    ind1 = calculate_indicators(data_1h)
    closes4 = np.array([x[4] for x in data_4h])
    ema20 = talib.EMA(closes4, timeperiod=20)[-1]
    ema50 = talib.EMA(closes4, timeperiod=50)[-1]
    ema200 = talib.EMA(closes4, timeperiod=200)[-1]

    direction = None
    if ind1['rsi'] > 60 and ind1['macd'] > ind1['macd_signal']:
        direction = 'long'
    elif ind1['rsi'] < 40 and ind1['macd'] < ind1['macd_signal']:
        direction = 'short'

    # 4시간봉 필터: 완전 반대 정렬이면 진입 금지
    if direction == 'long' and ema20 < ema50 < ema200:
        return None
    if direction == 'short' and ema20 > ema50 > ema200:
        return None

    return direction

def calculate_tp_sl(price, adx, direction):
    # 보수적 유동 배수
    if adx >= 25:
        tp_mul, sl_mul = 3.0, 1.5
    elif adx >= 20:
        tp_mul, sl_mul = 2.5, 1.2
    else:
        tp_mul, sl_mul = 2.0, 1.0
    atr = price * 0.005  # 단순 ATR 대체
    if direction == 'long':
        tp = price + atr * tp_mul
        sl = price - atr * sl_mul
    else:
        tp = price - atr * tp_mul
        sl = price + atr * sl_mul
    return round(tp, 2), round(sl, 2)

def get_price(symbol):
    return float(binance.fetch_ticker(symbol)['last'])

def open_position(symbol, direction):
    price = get_price(symbol)
    amount = 10 / price
    ind1h = calculate_indicators(get_ohlcv(symbol, '1h'))
    tp, sl = calculate_tp_sl(price, ind1h['adx'], direction)
    # 진입
    binance.create_market_order(symbol, 'buy' if direction=='long' else 'sell', amount)
    send_telegram(f"🚀 진입: {symbol} / {direction.upper()}\n진입가: {price}\nTP: {tp} / SL: {sl}")
    open_positions[symbol] = {
        'entry': price,
        'amount': amount,
        'side': direction,
        'entry_time': time.time(),
        'rechecked': False
    }

def close_position(symbol, reason):
    order = open_positions.pop(symbol, None)
    if not order: return
    close_side = 'sell' if order['side']=='long' else 'buy'
    binance.create_market_order(symbol, close_side, order['amount'])
    profit = (get_price(symbol) - order['entry']) * order['amount'] * (1 if order['side']=='long' else -1)
    trade_history.append({'symbol': symbol, 'profit': profit, 'time': time.time()})
    send_telegram(f"{reason} - {symbol} / 수익: {round(profit,2)} USDT")

def monitor_positions():
    while True:
        now = time.time()
        for sym, data in list(open_positions.items()):
            elapsed = now - data['entry_time']
            # 1.5시간 재검토
            if elapsed >= 5400 and not data['rechecked']:
                data['rechecked'] = True
                sig = get_signal(sym)
                if sig and sig != data['side']:
                    close_position(sym, "🧐 재판단 EXIT")
            # 2시간 무조건 청산
            elif elapsed >= 7200:
                close_position(sym, "⏱ TIMEOUT EXIT")
        time.sleep(1)

def trade_loop():
    while True:
        markets = binance.load_markets()
        for sym in markets:
            if '/USDT' in sym and sym not in open_positions:
                sig = get_signal(sym)
                if sig:
                    open_position(sym, sig)
                    time.sleep(1)
        time.sleep(10)

def daily_report():
    seoul = pytz.timezone('Asia/Seoul')
    while True:
        now = datetime.now(seoul)
        hhmm = now.strftime('%H:%M')
        # 아침 점호 06:30
        if hhmm == '06:30':
            # 기간: 전날 21:30 ~ 당일 06:30
            end_ts = now.timestamp()
            start = now - timedelta(hours=9)  # UTC: 21:30 전날
            start = start.replace(hour=21, minute=30, second=0, microsecond=0)
            start_ts = start.timestamp()
            _send_period(start_ts, end_ts, now, "아침 점호")
            time.sleep(60)
        # 저녁 점호 21:30
        elif hhmm == '21:30':
            # 기간: 당일 06:30 ~ 21:30
            start = now.replace(hour=6, minute=30, second=0, microsecond=0)
            start_ts = start.timestamp()
            end_ts = now.timestamp()
            _send_period(start_ts, end_ts, now, "저녁 점호")
            time.sleep(60)
        time.sleep(10)

def _send_period(start_ts, end_ts, now, title):
    trades = [t for t in trade_history if start_ts <= t['time'] <= end_ts]
    total = len(trades)
    wins = sum(1 for t in trades if t['profit']>0)
    losses = total - wins
    profit = sum(t['profit'] for t in trades)
    winrate = round(wins/total*100,2) if total else 0.0
    # 전체 승률 (5월29일 00:00 이후)
    kst = pytz.timezone('Asia/Seoul')
    base = datetime(now.year, now.month, now.day, tzinfo=kst)
    if now.hour < 0:  # 날짜 바뀔 때 처리
        base -= timedelta(days=1)
    base_ts = base.timestamp()
    overall = [t for t in trade_history if t['time'] >= base_ts]
    ow_total = len(overall)
    ow_wins = sum(1 for t in overall if t['profit']>0)
    overall_rate = round(ow_wins/ow_total*100,2) if ow_total else 0.0

    msg = f"📊<{title}> {now.strftime('%m월 %d일 %H:%M')}\n"
    msg += f"거래: {total}회  손익: {round(profit,2)} USDT\n"
    msg += f"{wins}승 {losses}패  승률: {winrate}%\n"
    msg += f"전체(오늘) 승률: {overall_rate}%"
    send_telegram(msg)

# === 실행 ===
threading.Thread(target=monitor_positions, daemon=True).start()
threading.Thread(target=daily_report, daemon=True).start()
trade_loop()
