# position_monitor.py
import threading
import time
import logging
from decimal import Decimal
from collections import deque
from binance_client import get_balance, cancel_all_orders_for_symbol, get_ohlcv, create_market_order, get_open_position_amt
from strategy import check_reversal_multi
from telegram_notifier import send_telegram
from config import MAX_TRADE_DURATION, EMERGENCY_PERIOD, EMERGENCY_DROP_PERCENT

class PositionMonitor(threading.Thread):
    """
    포지션별 긴급 탈출 및 반전 신호 감시
    - 5초 간격으로 체크 (잔고 샘플링 최적화)
    """
    def __init__(self, positions, positions_lock):
        super().__init__()
        self.daemon = True
        self.positions = positions
        self.positions_lock = positions_lock
        self.balance_history = deque()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                # 深度 드로우다운 체크 (5초 주기)
                current_balance = Decimal(str(get_balance()))
                now = time.time()
                self.balance_history.append((now, current_balance))
                while self.balance_history and (now - self.balance_history[0][0]) > EMERGENCY_PERIOD:
                    self.balance_history.popleft()
                if len(self.balance_history) >= 2:
                    oldest_ts, oldest_bal = self.balance_history[0]
                    drawdown = (oldest_bal - current_balance) / oldest_bal if oldest_bal > 0 else Decimal("0")
                    if drawdown >= EMERGENCY_DROP_PERCENT:
                        logging.error(f"[긴급 손실] {drawdown * 100:.2f}% 손실 → 청산 후 종료")
                        send_telegram(f"<b>🚨 긴급 손실 {drawdown * 100:.2f}% 발생</b>\\n포지션 전량 청산, 봇 종료")
                        with self.positions_lock:
                            symbols = list(self.positions.keys())
                        for symbol in symbols:
                            cancel_all_orders_for_symbol(symbol)
                            amt = get_open_position_amt(symbol)
                            if amt > 0:
                                create_market_order(symbol, "SELL", amt, reduceOnly=True)
                            with self.positions_lock:
                                self.positions.pop(symbol, None)
                        return

                # 각 포지션별 모니터링
                with self.positions_lock:
                    current_positions = dict(self.positions)
                for symbol, pos in current_positions.items():
                    side = pos['side']
                    entry_price = pos['entry_price']
                    start_time = pos['start_time']
                    quantity = pos['quantity']

                    # 보유시간 초과
                    if time.time() - start_time >= MAX_TRADE_DURATION:
                        cancel_all_orders_for_symbol(symbol)
                        amt = get_open_position_amt(symbol)
                        if amt > 0:
                            create_market_order(symbol, "SELL" if side == "long" else "BUY", amt, reduceOnly=True)
                        with self.positions_lock:
                            self.positions.pop(symbol, None)
                        continue

                    # 60초 이후 반전 감시 (다중 지표)
                    if time.time() - start_time > 60:
                        df1 = get_ohlcv(symbol, '1m', limit=50)
                        if df1 is not None and len(df1) >= 50:
                            if check_reversal_multi(df1, threshold=2):
                                logging.info(f"{symbol} 다중 반전 신호 감지 → 청산")
                                send_telegram(f"🔁 반전 신호 감지: {symbol} 청산")
                                cancel_all_orders_for_symbol(symbol)
                                amt = get_open_position_amt(symbol)
                                if amt > 0:
                                    create_market_order(symbol, "SELL" if side == "long" else "BUY", amt, reduceOnly=True)
                                with self.positions_lock:
                                    self.positions.pop(symbol, None)
                                continue

                time.sleep(5)
            except Exception as e:
                logging.error(f"[PositionMonitor 오류] {e}")
                time.sleep(5)
