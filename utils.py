# utils.py - 실전 매매 유틸리티 함수 모음

import time
from datetime import datetime
from binance_api import get_symbol_min_qty

# 현재 시각 문자열 반환 (로그용)
def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 슬리피지 적용 진입 가격 계산
def apply_slippage(price, side, slippage_pct=0.001):
    if side == "BUY":
        return round(price * (1 + slippage_pct), 2)
    else:
        return round(price * (1 - slippage_pct), 2)

# 진입 수량 계산 (잔고, 가격, 레버리지 기반)
def calculate_quantity(usdt_balance, price, leverage, symbol):
    try:
        notional = usdt_balance * leverage
        qty = notional / price

        # 최소 수량 반올림 적용
        min_qty = get_symbol_min_qty(symbol)
        if min_qty is None or qty < float(min_qty):
            return 0
        precision = len(min_qty.split('.')[-1])
        return round(qty, precision)
    except Exception as e:
        print(f"[수량 계산 오류] {symbol}: {e}")
        return 0

# TP/SL 가격 계산 (리스크 리워드 2:1 기준)
def calculate_tp_sl(entry_price, side, rr_ratio=2.0, sl_pct=0.01):
    if side == "BUY":
        stop_loss = round(entry_price * (1 - sl_pct), 2)
        take_profit = round(entry_price * (1 + sl_pct * rr_ratio), 2)
    else:
        stop_loss = round(entry_price * (1 + sl_pct), 2)
        take_profit = round(entry_price * (1 - sl_pct * rr_ratio), 2)
    return take_profit, stop_loss
