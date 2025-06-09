# binance_client.py
from binance.client import Client
import pandas as pd
from config import BINANCE_API_KEY, BINANCE_API_SECRET, LEVERAGE

# 바이낸스 클라이언트 생성
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
client.FUTURES_URL = 'https://fapi.binance.com'

# 심볼별 레버리지 설정
def set_leverage(symbols):
    for sym in symbols:
        try:
            client.futures_change_leverage(symbol=sym, leverage=LEVERAGE)
        except Exception as e:
            print(f"[Leverage Error] {sym}: {e}")

# 캔들 데이터 가져오기
def get_klines(symbol, interval, limit=100):
    data = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_asset_vol','num_trades','taker_base_vol','taker_quote_vol','ignore'
    ])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df[['open_time','open','high','low','close','volume']]

# 시장가 주문 실행
def place_order(symbol, side, quantity):
    return client.futures_create_order(
        symbol=symbol,
        side=side,
        type='MARKET',
        quantity=quantity
    )

# 오픈 포지션 조회
def get_open_position(symbol):
    pos = client.futures_position_information(symbol=symbol)
    for p in pos:
        amt = float(p['positionAmt'])
        if amt != 0:
            return p
    return None

# 현재 마크 가격 조회
def get_mark_price(symbol):
    res = client.futures_mark_price(symbol=symbol)
    return float(res['markPrice'])

# SL/TP 설정 (STOP_MARKET과 TAKE_PROFIT_MARKET 이용)
def set_sl_tp(symbol, side, sl_price, tp_price, quantity):
    try:
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='STOP_MARKET',
            stopPrice=sl_price,
            closePosition=True
        )
        client.futures_create_order(
            symbol=symbol,
            side=side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=tp_price,
            closePosition=True
        )
    except Exception as e:
        print(f"[SL/TP Error] {symbol}: {e}")

# 잔고 조회 함수 (USDT 잔고 확인용)
def get_balance():
    balances = client.futures_account_balance()
    for b in balances:
        if b['asset'] == 'USDT':
            return float(b['balance'])
    return 0.0
