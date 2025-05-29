# main.py
import os
import asyncio
import ccxt
import pandas as pd
import numpy as np
import time
import datetime
import schedule
from dotenv import load_dotenv
from telegram import Bot
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

open_positions = {}
trade_history = []

async def send_telegram(text):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

def fetch_ohlcv(symbol, timeframe='15m', limit=100):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

def calculate_indicators(df):
    df['rsi'] = RSIIndicator(df['close'], 14).rsi()
    macd = MACD(df['close'])
    df['macd'] = macd.macd_diff()
    df['ema'] = EMAIndicator(df['close'], 20).ema_indicator()
    df['stoch_k'] = StochasticOscillator(df['high'], df['low'], df['close']).stoch()
    df['adx'] = ADXIndicator(df['high'], df['low'], df['close'], 14).adx()
    return df

def check_entry(df_15m, df_1h):
    if df_15m.empty or df_1h.empty:
        return None

    last = df_15m.iloc[-1]
    last_h = df_1h.iloc[-1]
    if last['rsi'] < 30 and last['macd'] > 0 and last['stoch_k'] < 20 and last['adx'] > 20:
        if last_h['rsi'] > 40:
            return 'long'
    elif last['rsi'] > 70 and last['macd'] < 0 and last['stoch_k'] > 80 and last['adx'] > 20:
        if last_h['rsi'] < 60:
            return 'short'
    return None

def place_order(symbol, side, amount, entry_price):
    tp_ratio = 1.5 if side == 'long' else -1.5
    sl_ratio = -0.8 if side == 'long' else 0.8

    tp_price = round(entry_price * (1 + tp_ratio / 100), 4)
    sl_price = round(entry_price * (1 + sl_ratio / 100), 4)
    position_side = 'BUY' if side == 'long' else 'SELL'

    try:
        order = exchange.create_market_order(symbol, position_side, amount)
        trade_time = datetime.datetime.now()
        open_positions[symbol] = {
            'side': side,
            'entry_price': entry_price,
            'amount': amount,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'entry_time': trade_time
        }
        asyncio.run(send_telegram(f"🚀 진입: {symbol}\n방향: {side}\n진입가: {entry_price:.4f}\nTP: {tp_price:.4f}\nSL: {sl_price:.4f}"))
    except Exception as e:
        print(f"[ERROR] 주문 실패 {symbol}: {e}")

def monitor_positions():
    now = datetime.datetime.now()
    for symbol in list(open_positions):
        pos = open_positions[symbol]
        price = exchange.fetch_ticker(symbol)['last']
        pnl = (price - pos['entry_price']) / pos['entry_price'] * 100 if pos['side'] == 'long' else (pos['entry_price'] - price) / pos['entry_price'] * 100
        elapsed = (now - pos['entry_time']).total_seconds()

        if elapsed >= 7200:
            close_position(symbol, price, pnl, "⏰ 2시간 경과 청산")
        elif elapsed >= 5400:
            # 1시간 반 경과 재판단
            df_15m = calculate_indicators(fetch_ohlcv(symbol, '15m'))
            df_1h = calculate_indicators(fetch_ohlcv(symbol, '1h'))
            new_signal = check_entry(df_15m, df_1h)
            if new_signal and new_signal != pos['side']:
                close_position(symbol, price, pnl, "🔄 반대 신호 감지 청산")

def close_position(symbol, price, pnl, reason):
    try:
        side = 'SELL' if open_positions[symbol]['side'] == 'long' else 'BUY'
        amount = open_positions[symbol]['amount']
        exchange.create_market_order(symbol, side, amount)
        trade_history.append({
            'symbol': symbol,
            'side': open_positions[symbol]['side'],
            'entry': open_positions[symbol]['entry_price'],
            'exit': price,
            'pnl': pnl,
            'timestamp': datetime.datetime.now()
        })
        asyncio.run(send_telegram(f"💰 청산: {symbol}\n수익률: {pnl:.2f}%\n사유: {reason}"))
        del open_positions[symbol]
    except Exception as e:
        print(f"[ERROR] 청산 실패 {symbol}: {e}")

def summary_report(start, end, label):
    history = [t for t in trade_history if start <= t['timestamp'] <= end]
    wins = sum(1 for t in history if t['pnl'] > 0)
    losses = sum(1 for t in history if t['pnl'] <= 0)
    total = wins + losses
    profit = sum(t['pnl'] for t in history)

    overall = [t for t in trade_history if t['timestamp'] >= datetime.datetime(2025, 5, 29)]
    owins = sum(1 for t in overall if t['pnl'] > 0)
    ototal = len(overall)
    orate = (owins / ototal * 100) if ototal else 0

    msg = f"📋 {label} 점호\n기간: {start.strftime('%H:%M')} ~ {end.strftime('%H:%M')}\n"
    msg += f"거래횟수: {total}, 손익합계: {profit:.2f}%\n"
    msg += f"승패: {wins}승 {losses}패, 승률: {(wins/total*100):.1f}%\n" if total else "승패 정보 없음\n"
    msg += f"📊 5월29일 이후 전체 승률: {orate:.1f}%"
    asyncio.run(send_telegram(msg))

def schedule_reports():
    now = datetime.datetime.now()
    today = now.date()
    schedule.every().day.at("06:30").do(lambda: summary_report(
        datetime.datetime.combine(today - datetime.timedelta(days=1), datetime.time(21, 30)),
        datetime.datetime.combine(today, datetime.time(6, 30)),
        "🌅 아침"
    ))
    schedule.every().day.at("21:30").do(lambda: summary_report(
        datetime.datetime.combine(today, datetime.time(6, 30)),
        datetime.datetime.combine(today, datetime.time(21, 30)),
        "🌇 저녁"
    ))

asyncio.run(send_telegram("📊 자동매매 봇이 시작되었습니다."))

# 실행 루프
schedule_reports()

while True:
    try:
        markets = exchange.load_markets()
        symbols = [s for s in markets if s.endswith("USDT") and "/USDT" in s]

        for symbol in symbols:
            if symbol in open_positions:
                continue
            df_15m = calculate_indicators(fetch_ohlcv(symbol, '15m'))
            df_1h = calculate_indicators(fetch_ohlcv(symbol, '1h'))
            signal = check_entry(df_15m, df_1h)
            if signal:
                price = df_15m.iloc[-1]['close']
                balance = exchange.fetch_balance()['total']['USDT']
                amount = round(balance * 10 / price, 3)
                place_order(symbol, signal, amount, price)

        monitor_positions()
        schedule.run_pending()
        time.sleep(1)

    except Exception as e:
        print(f"[ERROR] 실행 중 오류: {e}")
        time.sleep(5)

