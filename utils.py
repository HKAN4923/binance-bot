import time
from datetime import datetime,timedelta
from binance_api import get_symbol_min_qty


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def apply_slippage(price, side, slippage_pct=0.001):
    if side == "BUY":
        return round(price * (1 + slippage_pct), 2)
    else:
        return round(price * (1 - slippage_pct), 2)

def calculate_quantity(usdt_balance, price, leverage, symbol):
    try:
        notional = usdt_balance * leverage
        qty = notional / price
        min_qty = get_symbol_min_qty(symbol)
        if min_qty is None or qty < float(min_qty):
            return 0
        precision = len(min_qty.split('.')[-1])
        return round(qty, precision)
    except Exception as e:
        print(f"[수량 계산 오류] {symbol}: {e}")
        return 0

def calculate_tp_sl(entry_price, side, rr_ratio=2.0, sl_pct=0.01):
    if side == "BUY":
        stop_loss = round(entry_price * (1 - sl_pct), 2)
        take_profit = round(entry_price * (1 + sl_pct * rr_ratio), 2)
    else:
        stop_loss = round(entry_price * (1 + sl_pct), 2)
        take_profit = round(entry_price * (1 - sl_pct * rr_ratio), 2)
    return take_profit, stop_loss

def to_kst(timestamp):
    """UTC timestamp → KST datetime"""
    return datetime.utcfromtimestamp(timestamp) + timedelta(hours=9)

def summarize_trades():
    try:
        with open("trades.log", "r") as f:
            lines = f.readlines()

        total = len(lines)
        wins = sum(1 for line in lines if "'reason': 'TP'" in line)
        losses = sum(1 for line in lines if "'reason': 'SL'" in line)
        pnl_sum = 0.0

        for line in lines:
            if "'exit_price':" in line and "'entry_price':" in line:
                try:
                    entry = float(line.split("'entry_price':")[1].split(",")[0])
                    exit_ = float(line.split("'exit_price':")[1].split(",")[0])
                    size = float(line.split("'position_size':")[1].split(",")[0]) if "'position_size':" in line else 1
                    direction = line.split("'side':")[1].split(",")[0].strip().strip("'")
                    diff = (exit_ - entry) if direction == "long" else (entry - exit_)
                    pnl_sum += diff * size
                except Exception:
                    pass

        win_rate = (wins / total * 100) if total else 0

        summary = (
            f"📊 누적 요약\n"
            f"▶ 총 트레이드: {total}\n"
            f"▶ 승: {wins} / 패: {losses} / 승률: {win_rate:.1f}%\n"
            f"▶ 누적 수익: {pnl_sum:.2f} USDT"
        )
        return summary

    except FileNotFoundError:
        return "📊 트레이드 로그 없음"

def log_trade(data):
    try:
        with open("trades.log", "a") as f:
            f.write(str(data) + "\n")
    except Exception as e:
        print(f"[로그 저장 오류] {e}")

import math
from binance_api import get_price, get_futures_balance, get_lot_size
from risk_config import POSITION_RATIO, LEVERAGE

def calculate_order_quantity(symbol):
    try:
        price = get_price(symbol)
        if price is None or price == 0:
            print(f"[{symbol}] 가격 조회 실패")
            return 0

        balance = get_futures_balance()
        base_value = balance * POSITION_RATIO
        order_value = base_value * LEVERAGE
        qty = order_value / price

        step_size = get_lot_size(symbol)
        if step_size is None:
            print(f"[{symbol}] 최소 수량 정보 없음")
            return 0

        precision = abs(int(round(-1 * math.log10(step_size))))
        final_qty = round(qty, precision)
        notional = final_qty * price

        if final_qty < step_size:
            print(f"[{symbol}] 수량 부족 → {final_qty} < {step_size}")
            return 0

        if notional < 20:
            print(f"[{symbol}] 금액 부족 → ${notional:.2f} < $20")
            return 0

        return final_qty
    except Exception as e:
        print(f"[{symbol}] 수량 계산 오류: {e}")
        return 0

def extract_entry_price(order_resp):
    try:
        if not order_resp:
            print("[주문 실패] 응답 없음")
            return None
        if float(order_resp.get("executedQty", 0)) == 0:
            print("[주문 실패] 체결되지 않음 (executedQty = 0)")
            return None
        return float(order_resp.get("avgFillPrice", 0))
    except Exception as e:
        print(f"[extract_entry_price 오류] {e}")
        return None
