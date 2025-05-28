# 수정된 전체 코드: precision 문제 해결 포함

import time
import math
from datetime import datetime, timedelta
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import os
import requests

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)

MAX_POSITIONS = 3
POSITION_SIZE_USD = 30 * 10  # 10배 레버리지 적용 시 실제 주문 금액은 300달러
ACTIVE_POSITIONS = {}

TELEGRAM_LAST_SENT = datetime.now() - timedelta(minutes=10)

# 심볼별 최소 수량, 소수점 자리수 정보 캐싱
symbol_info_cache = {}
def get_symbol_info(symbol):
    if symbol not in symbol_info_cache:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                symbol_info_cache[symbol] = s
                break
    return symbol_info_cache[symbol]

def round_quantity(symbol, quantity):
    info = get_symbol_info(symbol)
    step_size = None
    for f in info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])
            break
    if step_size:
        precision = int(round(-math.log(step_size, 10)))
        return round(quantity, precision)
    return quantity

def get_trade_signal(symbol):
    # 간단한 예시: 무조건 롱 시그널
    return 'buy'

def calculate_qty(symbol, usdt_amount):
    price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
    qty = usdt_amount / price
    return round_quantity(symbol, qty)

def enter_trade(symbol, signal):
    if symbol in ACTIVE_POSITIONS:
        return

    qty = calculate_qty(symbol, POSITION_SIZE_USD)
    side = SIDE_BUY if signal == 'buy' else SIDE_SELL

    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=qty
        )
        ACTIVE_POSITIONS[symbol] = {
            'entry_time': datetime.now(),
            'side': signal,
            'quantity': qty
        }
        send_telegram(f"진입: {symbol} | 방향: {signal} | 수량: {qty}")
    except BinanceAPIException as e:
        print(f"주문 실패: {e}")

def exit_trade(symbol):
    pos = ACTIVE_POSITIONS.get(symbol)
    if not pos:
        return

    exit_side = SIDE_SELL if pos['side'] == 'buy' else SIDE_BUY
    try:
        client.futures_create_order(
            symbol=symbol,
            side=exit_side,
            type=ORDER_TYPE_MARKET,
            quantity=pos['quantity']
        )
        send_telegram(f"청산: {symbol} | 방향: {pos['side']} | 수량: {pos['quantity']}")
        del ACTIVE_POSITIONS[symbol]
    except BinanceAPIException as e:
        print(f"청산 실패: {e}")

def send_telegram(message):
    global TELEGRAM_LAST_SENT
    now = datetime.now()
    if (now - TELEGRAM_LAST_SENT).total_seconds() >= 600:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=data)
        TELEGRAM_LAST_SENT = now

def monitor_positions():
    now = datetime.now()
    for symbol, data in list(ACTIVE_POSITIONS.items()):
        entry_time = data['entry_time']
        held_minutes = (now - entry_time).total_seconds() / 60

        if held_minutes >= 180:
            exit_trade(symbol)
        elif held_minutes >= 150:
            # 2시간 30분 이상 보유: 손익 판단 후 결정 (예시: 그냥 무조건 청산)
            exit_trade(symbol)


def main():
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    while True:
        monitor_positions()

        for symbol in symbols:
            if len(ACTIVE_POSITIONS) >= MAX_POSITIONS:
                break
            signal = get_trade_signal(symbol)
            enter_trade(symbol, signal)

        time.sleep(1)

if __name__ == '__main__':
    main()
