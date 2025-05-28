import os
import time
import math
import requests
import threading
from datetime import datetime, timedelta, timezone
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv
from binance.enums import (
    SIDE_BUY, SIDE_SELL,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET
)


# .env 환경 변수 로딩
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)

# 설정값
BALANCE = 100  # 가정 계좌 금액 (USD)
LEVERAGE = 10
RISK_PER_TRADE = 0.3  # 최대 진입 자산 비율
TRADE_SYMBOL_LIMIT = 3
ANALYSIS_INTERVAL = 1  # 분석 간격 (초)
TELEGRAM_INTERVAL = 600  # 10분에 한 번 메시지
TP_SL_RATIO = 1.3

active_trades = {}
last_telegram = datetime.now(timezone.utc) - timedelta(seconds=TELEGRAM_INTERVAL)


def send_telegram_message(message):
    global last_telegram
    now = datetime.now(timezone.utc)
    if (now - last_telegram).total_seconds() >= TELEGRAM_INTERVAL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        last_telegram = now


def get_precision(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    return float(f['stepSize'])
    return 0.01


def round_step_size(quantity, step_size):
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)


def analyze_market():
    # 여기에 전략을 적용해 진입 심볼을 선정하는 코드 작성 (임시로 BTCUSDT 하나 고정)
    return ["BTCUSDT"]


def get_trade_quantity(symbol):
    price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    amount = BALANCE * RISK_PER_TRADE * LEVERAGE / price
    step = get_precision(symbol)
    return round_step_size(amount, step)


def enter_trade(symbol):
    if symbol in active_trades:
        return
    qty = get_trade_quantity(symbol)
    price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    tp_price = round(price * (1 + 0.013), 2)
    sl_price = round(price * (1 - 0.01), 2)

    try:
        client.futures_create_order(symbol=symbol, side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=qty)
        client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                                    quantity=qty, stopPrice=tp_price, timeInForce=TIME_IN_FORCE_GTC)
        client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_STOP_MARKET,
                                    quantity=qty, stopPrice=sl_price, timeInForce=TIME_IN_FORCE_GTC)

        active_trades[symbol] = {
            'entry_time': datetime.now(timezone.utc),
            'qty': qty
        }
        send_telegram_message(f"[진입] {symbol} @ {price}, TP: {tp_price}, SL: {sl_price}")
    except Exception as e:
        send_telegram_message(f"[주문 실패] {symbol}: {e}")


def manage_trades():
    now = datetime.now(timezone.utc)
    for symbol in list(active_trades.keys()):
        entry_time = active_trades[symbol]['entry_time']
        age = (now - entry_time).total_seconds()

        if age > 3 * 3600:
            qty = active_trades[symbol]['qty']
            try:
                client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=qty)
                send_telegram_message(f"[청산 - 만료] {symbol} 3시간 경과")
                del active_trades[symbol]
            except:
                pass
        elif age > 2.5 * 3600:
            # 간단한 수익 판단 로직 (가정)
            entry_price = float(client.futures_position_information(symbol=symbol)[0]['entryPrice'])
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            pnl = (current_price - entry_price) * active_trades[symbol]['qty']

            if pnl > 0:
                qty = active_trades[symbol]['qty']
                try:
                    client.futures_create_order(symbol=symbol, side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=qty)
                    send_telegram_message(f"[청산 - 이익 실현] {symbol} 2.5시간 경과")
                    del active_trades[symbol]
                except:
                    pass


def main():
    while True:
        try:
            manage_trades()
            symbols = analyze_market()
            for symbol in symbols:
                if len(active_trades) < TRADE_SYMBOL_LIMIT:
                    enter_trade(symbol)
        except Exception as e:
            print(f"오류 발생: {e}")
        time.sleep(ANALYSIS_INTERVAL)


if __name__ == '__main__':
    main()
