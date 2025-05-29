# utils/strategy.py

from datetime import datetime
from config import RISK_RATIO, LEVERAGE
from .binance_api import fetch_ohlcv, fetch_ticker, create_market_order, create_tp_sl_orders
from .indicators import calc_indicators

def check_entry(symbol):
    df = calc_indicators(fetch_ohlcv(symbol, KLINE_INTERVAL_ENTRY))
    if df.empty or df["adx"].iloc[-1] < 20:
        return None
    last = df.iloc[-1]
    ls = sum([last["rsi"]<40, last["macd_diff"]>0, last["c"]>last["ema_long"], last["stoch"]<20])
    ss = sum([last["rsi"]>60, last["macd_diff"]<0, last["c"]<last["ema_long"], last["stoch"]>80])
    cl = sum([last["macd_diff"]>0, last["c"]>last["ema_long"], last["adx"]>20])
    cs = sum([last["macd_diff"]<0, last["c"]<last["ema_long"], last["adx"]>20])
    if cl>=2 and ls>=3: return "long"
    if cs>=2 and ss>=3: return "short"
    return None

def dynamic_tp_sl(entry_price, adx, side):
    if adx >= 25:
        tp_mul, sl_mul = 3.0, 1.5
    elif adx >= 20:
        tp_mul, sl_mul = 2.5, 1.2
    else:
        tp_mul, sl_mul = 2.0, 1.0
    atr = entry_price * 0.005
    if side=="long":
        tp = entry_price + atr*tp_mul
        sl = entry_price - atr*sl_mul
    else:
        tp = entry_price - atr*tp_mul
        sl = entry_price + atr*sl_mul
    return round(tp,4), round(sl,4)

def enter_position(symbol, side, positions, send_telegram):
    price = fetch_ticker(symbol)
    balance = fetch_balance()["total"]["USDT"]  # 직접 수정 필요 시 로컬에서
    amount  = round(balance * RISK_RATIO * LEVERAGE / price, 3)
    df = calc_indicators(fetch_ohlcv(symbol, KLINE_INTERVAL_ENTRY))
    if df.empty:
        return
    adx = df["adx"].iloc[-1]
    tp, sl = dynamic_tp_sl(price, adx, side)

    create_market_order(symbol, side, amount)
    create_tp_sl_orders(symbol, side, amount, tp, sl)

    now = datetime.now()
    positions[symbol] = {"side":side,"entry_price":price,"amount":amount,"entry_time":now,"last_monitor":now}
    send_telegram(f"🔹 ENTRY {symbol} | {side.upper()}\nEntry: {price:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}")
