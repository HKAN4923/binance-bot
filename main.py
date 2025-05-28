import os
import time
import pytz
import schedule
import logging
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import telegram

# Load environment
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)
bot = telegram.Bot(token=TELEGRAM_TOKEN)
KST = pytz.timezone('Asia/Seoul')

positions = {}
trade_history = []

def send_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")

def get_symbols():
    info = client.futures_exchange_info()
    usdt_pairs = [s['symbol'] for s in info['symbols']
                  if s['quoteAsset'] == 'USDT' and s['contractType'] == 'PERPETUAL']
    volumes = {}
    for symbol in usdt_pairs:
        try:
            trades = client.futures_ticker_24hr(symbol=symbol)
            volumes[symbol] = float(trades['quoteVolume'])
        except:
            continue
    sorted_symbols = sorted(volumes.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in sorted_symbols[:100]]

def fetch_ohlcv(symbol, interval='1m', limit=100):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df.astype(float)
    return df

def get_signal(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    last = df.iloc[-1]
    if last['ema9'] > last['ema21'] and last['rsi'] < 70:
        return 'LONG'
    elif last['ema9'] < last['ema21'] and last['rsi'] > 30:
        return 'SHORT'
    return None

def dynamic_tp_sl(symbol, entry_price, side):
    tp_rate = 0.012
    sl_rate = 0.006
    if side == 'LONG':
        tp = entry_price * (1 + tp_rate)
        sl = entry_price * (1 - sl_rate)
    else:
        tp = entry_price * (1 - tp_rate)
        sl = entry_price * (1 + sl_rate)
    return round(tp, 4), round(sl, 4)

def place_order(symbol, signal):
    try:
        balance = float(client.futures_account_balance()[1]['balance'])
        price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
        qty = round((balance * 0.1 * 10) / price, 3)
        side = SIDE_BUY if signal == 'LONG' else SIDE_SELL
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
        )
        entry_price = float(order['fills'][0]['price'])
        tp, sl = dynamic_tp_sl(symbol, entry_price, signal)
        tp_order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if signal == 'LONG' else SIDE_BUY,
            type=ORDER_TYPE_TAKE_PROFIT_MARKET,
            stopPrice=tp,
            closePosition=True,
            timeInForce='GTC'
        )
        sl_order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if signal == 'LONG' else SIDE_BUY,
            type=ORDER_TYPE_STOP_MARKET,
            stopPrice=sl,
            closePosition=True,
            timeInForce='GTC'
        )
        positions[symbol] = {
            'side': signal,
            'entry_time': datetime.now(),
            'entry_price': entry_price,
            'tp': tp,
            'sl': sl,
            'qty': qty
        }
        send_message(f"✅ 진입: {symbol} {signal}\n가격: {entry_price}\nTP: {tp} / SL: {sl}")
    except BinanceAPIException as e:
        print(e)

def monitor_positions():
    to_remove = []
    for symbol, pos in positions.items():
        elapsed = (datetime.now() - pos['entry_time']).total_seconds()
        pnl = check_pnl(symbol, pos['entry_price'], pos['side'], pos['qty'])
        if int(elapsed) % 1800 < 2:  # 30분마다
            send_message(f"📊 {symbol} 수익률: {pnl:.2f}%")
        if elapsed >= 7200:
            close_position(symbol, pos)
            to_remove.append(symbol)
    for s in to_remove:
        del positions[s]

def check_pnl(symbol, entry_price, side, qty):
    current_price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
    change = (current_price - entry_price) / entry_price * 100
    return change if side == 'LONG' else -change

def close_position(symbol, pos):
    side = SIDE_SELL if pos['side'] == 'LONG' else SIDE_BUY
    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=pos['qty'],
            reduceOnly=True
        )
        result = check_pnl(symbol, pos['entry_price'], pos['side'], pos['qty'])
        trade_history.append({
            'symbol': symbol,
            'side': pos['side'],
            'pnl': result,
            'time': datetime.now(KST)
        })
        send_message(f"💥 청산: {symbol} | 수익률: {result:.2f}%")
    except Exception as e:
        print(f"[ERROR] close failed: {e}")

def point_report(start, end, label):
    records = [t for t in trade_history if start <= t['time'] <= end]
    if not records:
        send_message(f"📋 [{label}] 거래 없음")
        return
    win = sum(1 for r in records if r['pnl'] > 0)
    lose = len(records) - win
    profit = sum(r['pnl'] for r in records)
    rate = win / len(records) * 100
    total = f"📊 [{label} 점호]\n총 거래: {len(records)}회\n손익: {profit:.2f}%\n{win}승 {lose}패 | 승률: {rate:.2f}%"
    total += alltime_report()
    send_message(total)

def alltime_report():
    after = datetime(2025, 5, 29, 0, 0, tzinfo=KST)
    records = [t for t in trade_history if t['time'] >= after]
    if not records:
        return ""
    win = sum(1 for r in records if r['pnl'] > 0)
    lose = len(records) - win
    rate = win / len(records) * 100
    return f"\n📅 전체 승률 (5/29 이후): {win}승 {lose}패 | {rate:.2f}%"

def morning_report():
    now = datetime.now(KST)
    start = now - timedelta(hours=9)  # 전날 21:30
    end = now.replace(hour=6, minute=30)
    point_report(start, end, "아침")

def evening_report():
    now = datetime.now(KST)
    start = now.replace(hour=6, minute=30)
    end = now.replace(hour=21, minute=30)
    point_report(start, end, "저녁")

def main_loop():
    symbols = get_symbols()
    for symbol in symbols:
        try:
            df1m = fetch_ohlcv(symbol, '1m')
            df1h = fetch_ohlcv(symbol, '1h')
            sig1m = get_signal(df1m)
            sig1h = get_signal(df1h)
            if sig1m and sig1h == sig1m:
                if symbol not in positions:
                    place_order(symbol, sig1m)
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
    monitor_positions()

# 스케줄
schedule.every(10).seconds.do(main_loop)
schedule.every().day.at("06:30").do(morning_report)
schedule.every().day.at("21:30").do(evening_report)

send_message("📢 봇 시작됨!")

while True:
    try:
        schedule.run_pending()
        time.sleep(1)
    except Exception as e:
        print(traceback.format_exc())
