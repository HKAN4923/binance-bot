import time
import requests
import math
import traceback
import logging
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# ===== 오류 방지용 직접 상수 정의 =====
ORDER_TYPE_STOP_MARKET = 'STOP_MARKET'
ORDER_TYPE_TAKE_PROFIT_MARKET = 'TAKE_PROFIT_MARKET'

# ===== 텔레그램 설정 =====
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=data)
        if not response.ok:
            print("텔레그램 전송 실패:", response.text)
    except Exception as e:
        print("텔레그램 전송 중 오류 발생:", e)

# ===== 환경 변수 로드 =====
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(API_KEY, API_SECRET)

# ===== 포지션 관리 =====
open_positions = {}
position_open_time = {}

# ===== 포지션 종료 =====
def close_position(symbol, side):
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=open_positions[symbol]['quantity'],
            reduceOnly=True
        )
        pnl = calculate_pnl(symbol, order['avgFillPrice'])
        send_telegram_message(f"[{symbol}] 포지션 종료\n손익: {pnl:.2f}%")
        del open_positions[symbol]
        del position_open_time[symbol]
    except Exception as e:
        send_telegram_message(f"[{symbol}] 종료 실패: {e}")
        print(traceback.format_exc())

def calculate_pnl(symbol, exit_price):
    entry = float(open_positions[symbol]['entry'])
    exit = float(exit_price)
    if open_positions[symbol]['side'] == SIDE_BUY:
        return (exit - entry) / entry * 100
    else:
        return (entry - exit) / entry * 100

# ===== 전략 =====
def check_entry(symbol):
    # 예시로 항상 False 반환
    return None

# ===== 진입 =====
def enter_position(symbol, side):
    try:
        ticker = client.futures_ticker_price(symbol=symbol)
        price = float(ticker['price'])

        balance = client.futures_account_balance()
        usdt_balance = float([b['balance'] for b in balance if b['asset'] == 'USDT'][0])
        leverage = 10
        quantity = round((usdt_balance * leverage) / price, 3)

        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )

        open_positions[symbol] = {
            'side': side,
            'quantity': quantity,
            'entry': order['avgFillPrice']
        }
        position_open_time[symbol] = datetime.now(pytz.timezone("Asia/Seoul"))

        # 스탑 및 익절 주문 설정
        stop_price = round(price * 0.97 if side == SIDE_BUY else price * 1.03, 2)
        take_profit_price = round(price * 1.05 if side == SIDE_BUY else price * 0.95, 2)

        client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,
            type=ORDER_TYPE_STOP_MARKET,
            stopPrice=stop_price,
            quantity=quantity,
            reduceOnly=True
        )
        client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,
            type=ORDER_TYPE_TAKE_PROFIT_MARKET,
            stopPrice=take_profit_price,
            quantity=quantity,
            reduceOnly=True
        )

        send_telegram_message(
            f"[{symbol}] {'롱' if side == SIDE_BUY else '숏'} 진입 완료\n진입가: {order['avgFillPrice']}\n스탑: {stop_price}\n익절: {take_profit_price}"
        )

    except BinanceAPIException as e:
        send_telegram_message(f"[{symbol}] 주문 실패: {e.message}")
    except Exception as e:
        send_telegram_message(f"[{symbol}] 진입 중 오류 발생: {e}")
        print(traceback.format_exc())

# ===== 메인 루프 =====
def run_bot():
    print("자동매매 봇 실행 중...")
    send_telegram_message("📢 자동매매 봇이 시작되었습니다.")
    symbols = [s['symbol'] for s in client.futures_exchange_info()['symbols'] if 'USDT' in s['symbol'] and s['contractType'] == 'PERPETUAL']

    while True:
        try:
            for symbol in symbols:
                if symbol in open_positions:
                    now = datetime.now(pytz.timezone("Asia/Seoul"))
                    elapsed = now - position_open_time[symbol]
                    if elapsed > timedelta(hours=2):
                        close_position(symbol, open_positions[symbol]['side'])
                    elif elapsed > timedelta(hours=1, minutes=30):
                        if not check_entry(symbol):
                            close_position(symbol, open_positions[symbol]['side'])
                    continue

                entry_signal = check_entry(symbol)
                if entry_signal:
                    enter_position(symbol, entry_signal)

            time.sleep(10)

        except KeyboardInterrupt:
            print("종료 요청됨. 봇을 종료합니다.")
            break
        except Exception as e:
            print("오류 발생:", e)
            print(traceback.format_exc())
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
