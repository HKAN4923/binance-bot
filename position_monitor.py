# position_monitor.py
import threading
import time
import logging
from decimal import Decimal
from collections import deque
from binance_client import get_balance, cancel_all_orders_for_symbol, get_ohlcv
from strategy import check_entry_with_confidence
from telegram_notifier import send_telegram
from config import MAX_TRADE_DURATION, EMERGENCY_PERIOD, EMERGENCY_DROP_PERCENT

class PositionMonitor:
    def __init__(self, positions, positions_lock, trade_log, trade_log_lock, close_callback):
        self.positions = positions
        self.positions_lock = positions_lock
        self.trade_log = trade_log
        self.trade_log_lock = trade_log_lock
        self.close_callback = close_callback
        self.stop_flag = threading.Event()
        self.balance_history = deque()

    def start(self):
        threading.Thread(target=self._monitor_positions, daemon=True).start()

    def stop(self):
        self.stop_flag.set()

    def _emergency_check(self):
        now = time.time()
        balance = Decimal(str(get_balance()))
        self.balance_history.append((now, balance))
        while self.balance_history and now - self.balance_history[0][0] > EMERGENCY_PERIOD:
            self.balance_history.popleft()
        if len(self.balance_history) >= 2:
            start_balance = self.balance_history[0][1]
            drop = (start_balance - balance) / start_balance
            if drop >= EMERGENCY_DROP_PERCENT:
                return True
        return False

    def _monitor_positions(self):
        while not self.stop_flag.is_set():
            try:
                if self._emergency_check():
                    send_telegram("⚠️ Emergency Stop: 10분 내 10% 이상 손실 감지. 봇 중단합니다.")
                    with self.positions_lock:
                        symbols = list(self.positions.keys())
                    for symbol in symbols:
                        cancel_all_orders_for_symbol(symbol)
                        with self.positions_lock:
                            self.positions.pop(symbol, None)
                    self.stop()
                    break

                with self.positions_lock:
                    symbols = list(self.positions.keys())

                for symbol in symbols:
                    with self.positions_lock:
                        pos = self.positions.get(symbol)
                    if not pos:
                        continue

                    qty = pos.get('quantity', 0)
                    if qty == 0:
                        with self.positions_lock:
                            self.positions.pop(symbol, None)
                        continue

                    start_time = pos.get('start_time', 0)
                    if time.time() - start_time > MAX_TRADE_DURATION:
                        send_telegram(f"⏳ 보유시간 초과: {symbol} 청산합니다.")
                        cancel_all_orders_for_symbol(symbol)
                        with self.positions_lock:
                            self.positions.pop(symbol, None)
                        continue

                    df1m = get_ohlcv(symbol, '1m', limit=50)
                    if df1m is not None:
                        sig_info = check_entry_with_confidence(df1m)
                        if sig_info.get('side') and sig_info['side'] != pos.get('side') and sig_info.get('confidence', 0) >= 0.8:
                            send_telegram(f"🔁 반대 신호 감지: {symbol} 청산합니다.")
                            cancel_all_orders_for_symbol(symbol)
                            with self.positions_lock:
                                self.positions.pop(symbol, None)
                            continue

                time.sleep(1)

            except Exception as e:
                logging.error(f"[모니터링 오류] {e}")
                time.sleep(1)

