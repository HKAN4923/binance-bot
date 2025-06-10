import os
import time
import logging
from dotenv import load_dotenv
from binance.client import Client
from requests.exceptions import RequestException, HTTPError

load_dotenv()

# Initialize Binance Futures Client with timeouts
CLIENT = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET"),
    requests_params={"timeout": (3, 5)}
)

# Configure leverage only for active USDT perpetual futures contracts
try:
    futures_info = CLIENT.futures_exchange_info()["symbols"]
    for s in futures_info:
        sym = s["symbol"]
        # Only perpetual USDT contracts in TRADING status
        if sym.endswith("USDT") and s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING":
            try:
                CLIENT.futures_change_leverage(
                    symbol=sym,
                    leverage=int(os.getenv("LEVERAGE", 5))
                )
                time.sleep(0.05)
            except HTTPError as e:
                logging.warning(f"Leverage set HTTP error for {sym}: {e}")
            except RequestException as e:
                logging.warning(f"Leverage set network error for {sym}: {e}")
            except Exception as e:
                logging.warning(f"Leverage set failed for {sym}: {e}")
except Exception as e:
    logging.error(f"Failed to set initial leverage configuration: {e}")


def get_account_balance() -> float:
    """
    Return current USDT balance from futures account.
    """
    bal = CLIENT.futures_account_balance()
    return float(next(x["balance"] for x in bal if x.get("asset") == "USDT"))


def get_open_position_amt(symbol: str) -> float:
    """
    Return absolute position amount for given symbol.
    """
    for p in CLIENT.futures_position_information(symbol=symbol):
        amt = float(p.get("positionAmt", 0))
        if amt != 0:
            return abs(amt)
    return 0.0


def get_mark_price(symbol: str) -> float:
    """
    Return current mark price for given symbol.
    """
    return float(CLIENT.futures_mark_price(symbol=symbol).get("markPrice", 0))


def get_klines(symbol: str, interval: str, limit: int):
    """
    Fetch kline/candlestick data with retries on network errors.
    Returns list of klines or empty list if all retries fail.
    """
    max_retries = 3
    delay = 1  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            return CLIENT.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
        except RequestException as e:
            logging.warning(f"get_klines attempt {attempt}/{max_retries} failed: {e}")
            time.sleep(delay)
    logging.error(f"get_klines failed after {max_retries} attempts for {symbol} {interval}")
    return []


def place_order(symbol: str, side: str, qty: float, stop_loss: float=None, take_profit: float=None):
    """
    Place market order and optional stop-loss/take-profit orders.
    """
    order = CLIENT.futures_create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty
    )
    if stop_loss is not None:
        CLIENT.futures_create_order(
            symbol=symbol,
            side=("SELL" if side == "BUY" else "BUY"),
            type="STOP_MARKET",
            stopPrice=stop_loss,
            closePosition=True
        )
    if take_profit is not None:
        CLIENT.futures_create_order(
            symbol=symbol,
            side=("SELL" if side == "BUY" else "BUY"),
            type="TAKE_PROFIT_MARKET",
            stopPrice=take_profit,
            closePosition=True
        )


def close_position(symbol: str, side: str, qty: float):
    """
    Close an open position by placing a market order with reduceOnly flag.
    Side argument is original position side.
    """
    closing_side = "SELL" if side == "BUY" else "BUY"
    CLIENT.futures_create_order(
        symbol=symbol,
        side=closing_side,
        type="MARKET",
        quantity=qty,
        reduceOnly=True
    )


def cancel_all_sltp(symbol: str=None):
    """
    Cancel all stop-loss and take-profit orders for symbol or all symbols.
    """
    open_orders = CLIENT.futures_get_open_orders(symbol=symbol) if symbol else CLIENT.futures_get_open_orders()
    for o in open_orders:
        if o.get("type") in ["TAKE_PROFIT_MARKET", "STOP_MARKET"]:
            try:
                CLIENT.futures_cancel_order(symbol=o["symbol"], orderId=o["orderId"])
            except Exception:
                pass
