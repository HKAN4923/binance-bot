import os
import time
import logging
from dotenv import load_dotenv
from binance.client import Client
from requests.exceptions import RequestException

load_dotenv()

# API Client with timeout settings
CLIENT = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET"),
    requests_params={"timeout": (3, 5)}  # (connect timeout, read timeout)
)

# USDT 페어에 대한 기본 레버리지 설정(최초 1회)
for s in CLIENT.get_exchange_info()["symbols"]:
    sym = s["symbol"]
    if sym.endswith("USDT"):
        try:
            CLIENT.futures_change_leverage(
                symbol=sym,
                leverage=int(os.getenv("LEVERAGE", 5))
            )
            time.sleep(0.05)
        except Exception as e:
            logging.warning(f"Leverage set failed for {sym}: {e}")


def get_open_position_amt(symbol: str) -> float:
    for p in CLIENT.futures_position_information(symbol=symbol):
        amt = float(p["positionAmt"])
        if amt != 0:
            return abs(amt)
    return 0.0


def get_mark_price(symbol: str) -> float:
    return float(CLIENT.futures_mark_price(symbol=symbol)["markPrice"])


def get_klines(symbol: str, interval: str, limit: int):
    """
    Fetch kline/candlestick data with retries on network errors.
    Returns list of klines or empty list if all retries fail.
    """
    max_retries = 3
    delay = 1  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            klines = CLIENT.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except RequestException as e:
            logging.warning(f"get_klines attempt {attempt}/{max_retries} failed: {e}")
            time.sleep(delay)
    logging.error(f"get_klines failed after {max_retries} attempts for {symbol} {interval}")
    return []


def place_order(symbol: str, side: str, qty: float, stop_loss: float=None, take_profit: float=None):
    order = CLIENT.futures_create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty
    )
    if stop_loss:
        CLIENT.futures_create_order(
            symbol=symbol,
            side=("SELL" if side=="BUY" else "BUY"),
            type="STOP_MARKET",
            stopPrice=stop_loss,
            closePosition=True
        )
    if take_profit:
        CLIENT.futures_create_order(
            symbol=symbol,
            side=("SELL" if side=="BUY" else "BUY"),
            type="TAKE_PROFIT_MARKET",
            stopPrice=take_profit,
            closePosition=True
        )


def cancel_all_sltp(symbol: str):
    open_orders = CLIENT.futures_get_open_orders(symbol=symbol)
    for o in open_orders:
        if o["type"] in ["TAKE_PROFIT_MARKET", "STOP_MARKET"]:
            try:
                CLIENT.futures_cancel_order(symbol=o["symbol"], orderId=o["orderId"])
            except Exception:
                pass
