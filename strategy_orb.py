from utils import calculate_quantity, apply_slippage, calculate_tp_sl, now_string
from binance_api import client
from position_manager import add_position, remove_position, get_open_positions
from risk_config import MAX_POSITIONS, TRADE_AMOUNT_RATIO, LEVERAGE, FILTER_RATIO

import time

entry_record = {}

def check_entry(symbol):
    if symbol in get_open_positions():
        return

    candles = client.futures_klines(symbol=symbol, interval="1m", limit=20)
    if len(candles) < 10:
        return

    open_range = candles[0]
    high = float(open_range[2])
    low = float(open_range[3])
    range_ = high - low

    current_price = float(candles[-1][4])
    upper_bound = high + range_ * 0.05

    if current_price > upper_bound:
        positions = get_open_positions()
        if len(positions) >= MAX_POSITIONS:
            return

        balance = float(client.futures_account_balance()[1]["balance"])
        qty = calculate_quantity(balance * TRADE_AMOUNT_RATIO, current_price, LEVERAGE, symbol)
        if qty == 0:
            return

        slippage_price = apply_slippage(current_price, "BUY")
        tp, sl = calculate_tp_sl(slippage_price, "BUY")

        order = client.futures_create_order(
            symbol=symbol,
            side="BUY",
            type="MARKET",
            quantity=qty
        )
        add_position(symbol, "BUY", slippage_price, qty, "ORB")
        client.futures_create_order(symbol=symbol, side="SELL", type="TAKE_PROFIT_MARKET", stopPrice=tp, closePosition=True)
        client.futures_create_order(symbol=symbol, side="SELL", type="STOP_MARKET", stopPrice=sl, closePosition=True)
        entry_record[symbol] = time.time()
        print(f"[{now_string()}][ORB 진입] {symbol} 가격: {slippage_price}")

def check_exit(symbol):
    positions = get_open_positions()
    if symbol not in positions:
        return
    if positions[symbol]["strategy"] != "ORB":
        return

    candles = client.futures_klines(symbol=symbol, interval="1m", limit=2)
    if len(candles) < 2:
        return

    high = float(candles[-2][2])
    low = float(candles[-2][3])
    current_price = float(candles[-1][4])

    if current_price < low or time.time() - entry_record.get(symbol, 0) > 60 * 180:
        client.futures_create_order(
            symbol=symbol,
            side="SELL",
            type="MARKET",
            quantity=positions[symbol]["qty"]
        )
        remove_position(symbol)
        print(f"[{now_string()}][ORB 청산] {symbol} 가격: {current_price}")
