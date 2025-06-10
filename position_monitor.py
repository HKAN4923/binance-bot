# position_monitor.py

import threading
import time
import logging
from decimal import Decimal
from collections import deque

from binance_client import (
    get_account_balance,
    cancel_all_sltp,
    get_open_position_amt,
    create_market_order,
    get_ohlcv
)
from strategy import check_reversal_multi
from telegram_notifier import send_telegram
from config import Config

class PositionMonitor(threading.Thread):
    """
    포지션별 긴급 탈출 및 반전 신호 감시
    """
    def __init__(self, positions, positions_lock):
        super().__init__(daemon=True)
        self.positions = positions
        self.lock = positions_lock
        self.balance_history = deque()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                # 1) 드로우다운 체크
                now = time.time()
                bal = Decimal(str(get_account_balance()))
                self.balance_history.append((now, bal))
                # EMERGENCY_PERIOD 이전 기록 삭제
                while self.balance_history and now - self.balance_history[0][0] > Config.EMERGENCY_PERIOD:
                    self.balance_history.popleft()
                if len(self.balance_history) >= 2:
                    oldest_ts, oldest_bal = self.balance_history[0]
                    drawdown = (oldest_bal - bal) / oldest_bal if oldest_bal > 0 else Decimal("0")
                    if drawdown >= Decimal(str(Config.EMERGENCY_DROP_PERCENT)):
                        send_telegram(f"🚨 긴급 손실 {drawdown*100:.2f}% 발생, 전체 청산 후 봇 종료")
                        with self.lock:
                            syms = list(self.positions.keys())
                        for s in syms:
                            cancel_all_sltp(s)
                            amt = get_open_position_amt(s)
                            if amt > 0:
                                create_market_order(s, "SELL", amt, reduceOnly=True)
                            with self.lock:
                                self.positions.pop(s, None)
                        return

                # 2) 반전 신호 체크
                with self.lock:
                    items = list(self.positions.items())
                for sym, pos in items:
                    if time.time() - pos.start_time < 60:
                        continue
                    df1 = get_ohlcv(sym, "1m", 50)
                    if df1 is None or len(df1) < 50:
                        continue
                    if check_reversal_multi(df1, threshold=3):
                        logging.info(f"{sym} 반전 신호 감지 → 청산")
                        send_telegram(f"🔁 반전 신호 감지: {sym} 청산")
                        cancel_all_sltp(sym)
                        amt = get_open_position_amt(sym)
                        if amt > 0:
                            create_market_order(sym, "SELL" if pos.side=="BUY" else "BUY", amt, reduceOnly=True)
                        with self.lock:
                            self.positions.pop(sym, None)

                time.sleep(5)

            except Exception as e:
                logging.error(f"[PositionMonitor 오류] {e}")
                time.sleep(5)
