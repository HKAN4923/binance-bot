import os
import time
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()

CLIENT = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

# USDT 페어만 5배(기본) 레버리지 설정 (최초 1회)
for s in CLIENT.get_exchange_info()["symbols"]:
    sym = s["symbol"]
    if sym.endswith("USDT"):
        try:
            CLIENT.futures_change_leverage(symbol=sym, leverage=int(os.getenv("LEVERAGE", 5)))
            time.sleep(0.05)
        except:
            pass

def get_account_balance() -> float:
    bal = CLIENT.futures_account_balance()
    return float(next(x for x in bal if x["asset"]=="USDT")["balance"])

def get_klines(symbol: str, interval: str, limit: int):
    return CLIENT.futures_klines(symbol=symbol, interval=interval, limit=limit)

def place_order(symbol: str, side: str, qty: float, stop_loss: float=None, take_profit: float=None):
    order = CLIENT.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=qty)
    if stop_loss:
        CLIENT.futures_create_order(
            symbol=symbol, side=("SELL" if side=="BUY" else "BUY"),
            type="STOP_MARKET", stopPrice=stop_loss, closePosition=True
        )
    if take_profit:
        CLIENT.futures_create_order(
            symbol=symbol, side=("SELL" if side=="BUY" else "BUY"),
            type="TAKE_PROFIT_MARKET", stopPrice=take_profit, closePosition=True
        )
    return order

def close_position(symbol: str, side: str, qty: float):
    CLIENT.futures_create_order(
        symbol=symbol, side=("SELL" if side=="BUY" else "BUY"),
        type="MARKET", quantity=qty, reduceOnly=True
    )
    cancel_all_sltp(symbol)

def cancel_all_sltp(symbol: str=None):
    orders = CLIENT.futures_get_open_orders(symbol=symbol) if symbol else CLIENT.futures_get_open_orders()
    for o in orders:
        if o["type"] in ["TAKE_PROFIT_MARKET","STOP_MARKET"]:
            try:
                CLIENT.futures_cancel_order(symbol=o["symbol"], orderId=o["orderId"])
            except:
                pass

def get_open_position_amt(symbol: str) -> float:
    for p in CLIENT.futures_position_information(symbol=symbol):
        amt = float(p["positionAmt"])
        if amt != 0:
            return abs(amt)
    return 0.0

def get_mark_price(symbol: str) -> float:
    return float(CLIENT.futures_mark_price(symbol=symbol)["markPrice"])
