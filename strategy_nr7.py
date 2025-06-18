from utils import calculate_quantity, apply_slippage, calculate_tp_sl, now_string
from binance_api import client
from position_manager import add_position, remove_position, get_open_positions
from risk_config import MAX_POSITIONS, TRADE_AMOUNT_RATIO, LEVERAGE, FILTER_RATIO

import time

entry_record = {}

def check_entry(symbol):
    if symbol in get_open_positions():
        return

    candles = client.futures_klines(symbol=symbol, interval="1h", limit=10)
    if len(candles) < 7:
        return

    ranges = [float(c[2]) - float(c[3]) for c in candles[-7:]]
    if ranges[-1] == min(ranges):
        current_price = float(candles[-1][4])
        balance = float(client.futures_account_balance()[1]["balance"])
        qty = calculate_quantity(balance * TRADE_AMOUNT_RATIO, current_price, LEVERAGE, symbol)
        if qty == 0 or len(get_open_positions()) >= MAX_POSITIONS:
            return

        slippage_price = apply_slippage(current_price, "BUY")
        tp, sl = calculate_tp_sl(slippage_price, "BUY")

        client.futures_create_order(symbol=symbol, side="BUY", type="MARKET", quantity=qty)
        add_position(symbol, "BUY", slippage_price, qty, "NR7")
        client.futures_create_order(symbol=symbol, side="SELL", type="TAKE_PROFIT_MARKET", stopPrice=tp, closePosition=True)
        client.futures_create_order(symbol=symbol, side="SELL", type="STOP_MARKET", stopPrice=sl, closePosition=True)
        entry_record[symbol] = time.time()
        print(f"[{now_string()}][NR7 진입] {symbol} 가격: {slippage_price}")

def check_exit(symbol):
    if symbol not in get_open_positions():
        return
    if get_open_positions()[symbol]["strategy"] != "NR7":
        return

    if time.time() - entry_record.get(symbol, 0) > 60 * 180:
        qty = get_open_positions()[symbol]["qty"]
        client.futures_create_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty)
        remove_position(symbol)
        print(f"[{now_string()}][NR7 청산] {symbol} 시간 초과 청산")
