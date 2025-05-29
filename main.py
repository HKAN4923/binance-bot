import os
import time
import datetime
import pytz
import threading
import traceback
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from telegram import Bot
from dotenv import load_dotenv

import pandas as pd
import numpy as np
import ta

# Load environment variables
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Initialize clients
client = Client(API_KEY, API_SECRET)
bot = Bot(token=TELEGRAM_TOKEN)

# Constants
MAX_TRADE_DURATION = 2 * 60 * 60  # 2시간
RECHECK_TIME = 1.5 * 60 * 60  # 1시간 반 후 재판단
TRADE_SYMBOLS_LIMIT = 100
LEVERAGE = 10
LOSS_LIMIT = 0.3  # 최대 손실 비율
PROFIT_TARGET = 0.03
LOSS_THRESHOLD = 0.015
POSITION_CHECK_INTERVAL = 1
ANALYSIS_INTERVAL = 10
TELEGRAM_REPORT_INTERVAL = 1800  # 30분
KST = pytz.timezone("Asia/Seoul")

positions = {}

def send_telegram(msg):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_top_symbols():
    tickers = client.futures_ticker()
    df = pd.DataFrame(tickers)
    df['quoteVolume'] = pd.to_numeric(df['quoteVolume'])
    df = df[df['symbol'].str.endswith("USDT") & ~df['symbol'].str.contains("1000")]
    top = df.sort_values("quoteVolume", ascending=False).head(TRADE_SYMBOLS_LIMIT)
    return list(top['symbol'])

def get_ohlcv(symbol, interval='5m', limit=100):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['volume'] = pd.to_numeric(df['volume'])
        return df
    except Exception as e:
        print(f"[{symbol}] get_ohlcv error: {e}")
        return None

def check_entry(df):
    try:
        df = df.copy()
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['ema'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close']).adx()

        last = df.iloc[-1]
        if last['rsi'] < 30 and last['macd'] > last['macd_signal'] and last['close'] > last['ema']:
            return 'long'
        elif last['rsi'] > 70 and last['macd'] < last['macd_signal'] and last['close'] < last['ema']:
            return 'short'
        return None
    except Exception as e:
        print("check_entry error:", e)
        return None

def place_order(symbol, side):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        balance = float(client.futures_account_balance()[6]['balance'])
        usdt = balance * 0.1  # 10% per trade
        price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
        quantity = round(usdt * LEVERAGE / price, 3)

        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY if side == 'long' else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        entry_price = float(order['avgFillPrice']) if 'avgFillPrice' in order else price
        positions[symbol] = {
            'side': side,
            'entry_price': entry_price,
            'entry_time': time.time(),
            'quantity': quantity,
            'notified': False,
        }
        send_telegram(f"✅ 진입: {symbol} | 방향: {side.upper()}\n📈 진입가: {entry_price:.4f}")
    except BinanceAPIException as e:
        print(f"Binance API error: {e}")
    except Exception as e:
        print(f"place_order error: {e}")

def check_positions():
    while True:
        now = time.time()
        for symbol, pos in list(positions.items()):
            try:
                price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
                entry = pos['entry_price']
                pnl = (price - entry) / entry if pos['side'] == 'long' else (entry - price) / entry
                elapsed = now - pos['entry_time']

                if pnl >= PROFIT_TARGET:
                    client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_SELL if pos['side'] == 'long' else SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=pos['quantity']
                    )
                    send_telegram(f"🎯 익절: {symbol}\n💰 수익률: {pnl*100:.2f}%")
                    del positions[symbol]
                elif pnl <= -LOSS_THRESHOLD or elapsed >= MAX_TRADE_DURATION:
                    client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_SELL if pos['side'] == 'long' else SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=pos['quantity']
                    )
                    send_telegram(f"🛑 손절/청산: {symbol}\n📉 수익률: {pnl*100:.2f}%")
                    del positions[symbol]
                elif elapsed >= TELEGRAM_REPORT_INTERVAL and not pos['notified']:
                    send_telegram(f"⏱️ 홀딩중: {symbol}\n현재 수익률: {pnl*100:.2f}%")
                    pos['notified'] = True

                if int(time.time()) % 30 == 0:
                    print(f"[{symbol}] 감시중... {pnl*100:.2f}% | {elapsed:.0f}s 경과")
            except Exception as e:
                print(f"[{symbol}] 감시 오류: {e}")
        time.sleep(POSITION_CHECK_INTERVAL)

def analyze_market():
    while True:
        start = time.time()
        print("📊 분석중...", end=" ")
        symbols = get_top_symbols()
        print(f"{len(symbols)}개 종목 | {datetime.datetime.now(KST).strftime('%H:%M:%S')}")
        for symbol in symbols:
            if symbol in positions:
                continue
            df = get_ohlcv(symbol)
            if df is None:
                continue
            signal = check_entry(df)
            if signal:
                place_order(symbol, signal)
        elapsed = time.time() - start
        time.sleep(max(0, ANALYSIS_INTERVAL - elapsed))

def send_daily_report():
    while True:
        now = datetime.datetime.now(KST)
        if now.hour == 6 and now.minute == 30:
            send_telegram("🌅 아침점호: 전일 야간 거래 요약\n(거래 횟수 및 손익 표시 예정)")
            time.sleep(60)
        elif now.hour == 21 and now.minute == 30:
            send_telegram("🌙 저녁점호: 금일 전체 거래 요약\n(승패 및 승률 표시 예정)")
            time.sleep(60)
        time.sleep(10)

if __name__ == "__main__":
    print("🚀 Binance 자동매매 봇 시작!")
    send_telegram("🤖 봇이 시작되었습니다.")

    threading.Thread(target=check_positions, daemon=True).start()
    threading.Thread(target=analyze_market, daemon=True).start()
    threading.Thread(target=send_daily_report, daemon=True).start()

    while True:
        time.sleep(60)
