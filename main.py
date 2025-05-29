import os
import time
import datetime
import pytz
import threading
import traceback
import asyncio
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from telegram import Bot
from dotenv import load_dotenv

import pandas as pd
import numpy as np
import ta

# ─── 환경 변수 로드 ──────────────────────────────────────────────────────────────
load_dotenv()
API_KEY          = os.getenv("BINANCE_API_KEY")
API_SECRET       = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ─── 클라이언트 초기화 ───────────────────────────────────────────────────────────
client = Client(API_KEY, API_SECRET)
bot    = Bot(token=TELEGRAM_TOKEN)

# ─── 상수 ─────────────────────────────────────────────────────────────────────────
MAX_TRADE_DURATION        = 2 * 60 * 60    # 2시간
RECHECK_TIME              = 1.5 * 60 * 60  # 1시간 반
LEVERAGE                  = 10
LOSS_THRESHOLD            = 0.015
PROFIT_TARGET             = 0.03
POSITION_CHECK_INTERVAL   = 1
ANALYSIS_INTERVAL         = 10
TELEGRAM_REPORT_INTERVAL  = 1800           # 30분
KST                       = pytz.timezone("Asia/Seoul")

positions = {}

# ─── 텔레그램 전송 (수정된 부분) ─────────────────────────────────────────────────
def send_telegram(msg):
    try:
        # Bot.send_message is a coroutine in this version; run it synchronously
        asyncio.get_event_loop().run_until_complete(
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        )
    except Exception as e:
        print(f"Telegram error: {e}")

# ─── 전체 선물 USDT 심볼 조회 ────────────────────────────────────────────────────
def get_all_symbols():
    tickers = client.futures_ticker()
    df = pd.DataFrame(tickers)
    df = df[df['symbol'].str.endswith("USDT")]
    return list(df['symbol'].unique())

# ─── OHLCV 조회 ─────────────────────────────────────────────────────────────────
def get_ohlcv(symbol, interval='5m', limit=100):
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['high']  = pd.to_numeric(df['high'])
        df['low']   = pd.to_numeric(df['low'])
        df['open']  = pd.to_numeric(df['open'])
        return df
    except Exception as e:
        print(f"[{symbol}] OHLCV error, 건너뜀: {e}")
        return None

# ─── 진입 시그널 판단 ───────────────────────────────────────────────────────────
def check_entry(df):
    try:
        df = df.copy()
        df['rsi']   = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        macd        = ta.trend.MACD(df['close'])
        df['macd']  = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['ema']   = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
        stoch       = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch'] = stoch.stoch()
        df['adx']   = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

        last = df.iloc[-1]
        if last['adx'] < 20:
            return None

        ls = sum([last["rsi"]<40, last["macd"]>last["macd_signal"], last["close"]>last["ema"], last["stoch"]<20])
        ss = sum([last["rsi"]>60, last["macd"]<last["macd_signal"], last["close"]<last["ema"], last["stoch"]>80])
        cl = sum([last["macd"]>last["macd_signal"], last["close"]>last["ema"], last["adx"]>20])
        cs = sum([last["macd"]<last["macd_signal"], last["close"]<last["ema"], last["adx"]>20])

        if cl >= 2 and ls >= 3:
            return "long"
        if cs >= 2 and ss >= 3:
            return "short"
        return None
    except Exception as e:
        print(f"check_entry error: {e}")
        return None

# ─── 주문 및 TP/SL 설정 ─────────────────────────────────────────────────────────
def place_order(symbol, side):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
        balance = float(next(b for b in client.futures_account_balance() if b['asset']=='USDT')['balance'])
        price   = float(client.futures_mark_price(symbol=symbol)['markPrice'])
        qty     = round(balance * 0.1 * LEVERAGE / price, 3)

        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY if side=="long" else SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=qty
        )
        entry_price = float(order.get('avgFillPrice', price))
        # TP/SL
        atr = entry_price * 0.005
        adx = check_entry(get_ohlcv(symbol, limit=100))  # reuse last adx
        if adx=="long" or adx=="short":
            tp_mul, sl_mul = (3.0,1.5) if adx=="long" else (2.5,1.2)
        else:
            tp_mul, sl_mul = 2.0,1.0
        tp = round(entry_price + atr*tp_mul if side=="long" else entry_price - atr*tp_mul, 4)
        sl = round(entry_price - atr*sl_mul if side=="long" else entry_price + atr*sl_mul, 4)

        client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=="long" else SIDE_BUY,
                                    type=ORDER_TYPE_TAKE_PROFIT_MARKET, stopPrice=tp, closePosition=True)
        client.futures_create_order(symbol=symbol, side=SIDE_SELL if side=="long" else SIDE_BUY,
                                    type=ORDER_TYPE_STOP_MARKET, stopPrice=sl, closePosition=True)

        positions[symbol] = {
            'side': side,
            'entry_price': entry_price,
            'quantity': qty,
            'entry_time': time.time(),
            'notified': False
        }
        send_telegram(f"🔹 ENTRY {symbol} | {side.upper()}\nEntry: {entry_price:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}")
    except Exception as e:
        print(f"[{symbol}] 주문 실패: {e}")

# ─── 포지션 모니터링 ───────────────────────────────────────────────────────────
def monitor_positions():
    while True:
        now = time.time()
        for sym, pos in list(positions.items()):
            try:
                mark = float(client.futures_mark_price(symbol=sym)['markPrice'])
                entry = pos['entry_price']
                pnl_ratio = (mark-entry)/entry if pos['side']=="long" else (entry-mark)/entry
                elapsed = now - pos['entry_time']

                # 이익 실현 / 손절 / 시간 청산
                if pnl_ratio >= PROFIT_TARGET or pnl_ratio <= -LOSS_THRESHOLD or elapsed >= MAX_TRADE_DURATION:
                    side_op = SIDE_SELL if pos['side']=="long" else SIDE_BUY
                    client.futures_create_order(symbol=sym, side=side_op, type=ORDER_TYPE_MARKET, quantity=pos['quantity'])
                    send_telegram(f"🔸 EXIT {sym} | PnL: {pnl_ratio*100:.2f}%")
                    del positions[sym]
                    continue

                # 홀드 중 알림
                if elapsed >= TELEGRAM_REPORT_INTERVAL and not pos['notified']:
                    send_telegram(f"⏱️ HOLDING {sym} | Current PnL: {pnl_ratio*100:.2f}%")
                    pos['notified'] = True

                # 터미널 출력
                if int(now) % 30 == 0:
                    print(f"[{sym}] 감시중... PnL: {pnl_ratio*100:.2f}% | 경과: {int(elapsed)}s")
            except Exception as e:
                print(f"[{sym}] 모니터링 오류, 건너뜀: {e}")
        time.sleep(POSITION_CHECK_INTERVAL)

# ─── 시장 분석 및 진입 ───────────────────────────────────────────────────────────
def analyze_market():
    while True:
        start = time.time()
        symbols = get_all_symbols()
        print(f"📊 분석중... {len(symbols)}개 종목 | {datetime.datetime.now(KST).strftime('%H:%M:%S')}")
        for sym in symbols:
            if sym in positions:
                continue
            df = get_ohlcv(sym)
            if df is None:
                continue
            sig = check_entry(df)
            if sig:
                place_order(sym, sig)
        elapsed = time.time() - start
        time.sleep(max(0, ANALYSIS_INTERVAL - elapsed))

# ─── 메인 ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Bot started")
    send_telegram("🤖 Bot started")

    threading.Thread(target=monitor_positions, daemon=True).start()
    threading.Thread(target=analyze_market, daemon=True).start()

    while True:
        time.sleep(60)
