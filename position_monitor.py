# 파일명: position_monitor.py
# 포지션 긴급 모니터링 모듈

import threading
import time
import logging
from collections import deque
from decimal import Decimal

from config import MAX_TRADE_DURATION, EMERGENCY_PERIOD, EMERGENCY_DROP_PERCENT
from utils import get_futures_balance as get_position_balance


from position_manager import get_open_positions, get_position
from telegram_bot import send_telegram
from binance_client import place_market_exit, cancel_all_orders_for_symbol



class PositionMonitor(threading.Thread):
    """
    포지션별 긴급 손실 및 보유시간 초과 감시
    """
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.balance_history = deque()
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                # 잔고 드로우다운 감시
                balance = Decimal(str(get_position_balance()))
                now = time.time()
                self.balance_history.append((now, balance))

                # 오래된 기록 제거
                while self.balance_history and (now - self.balance_history[0][0]) > EMERGENCY_PERIOD:
                    self.balance_history.popleft()

                # 손실률 계산
                if len(self.balance_history) >= 2:
                    old_ts, old_bal = self.balance_history[0]
                    drawdown = (old_bal - balance) / old_bal if old_bal > 0 else Decimal(0)
                    if drawdown >= EMERGENCY_DROP_PERCENT:
                        send_telegram(f"🚨 긴급 손실 {drawdown*100:.2f}% 발생, 모든 포지션 청산")
                        self._liquidate_all()
                        return

                # 각 포지션별 최대 보유시간 초과 감시
                for sym, pos in list(get_open_positions().items()):
                    entry_time = pos.get("entry_time", 0)
                    qty = pos.get("qty", 0)
                    direction = pos.get("side")
                    if time.time() - entry_time >= MAX_TRADE_DURATION:
                        send_telegram(f"⏰ {sym} 보유시간 초과, 청산 진행")
                        place_market_exit(sym, "SELL" if direction == "long" else "BUY", qty)
                        if sym in get_open_positions():
                            cancel_all_orders_for_symbol(sym)

                time.sleep(5)
            except Exception as e:
                logging.error(f"[PositionMonitor 오류] {e}")
                time.sleep(5)

    def _liquidate_all(self) -> None:
        for sym in list(get_open_positions().keys()):
            pos = get_position(sym)
            qty = pos.get("qty", 0)
            place_market_exit(sym, "SELL" if pos.get("side") == "long" else "BUY", qty)
            cancel_all_orders_for_symbol(sym)

    def stop(self) -> None:
        self._stop_event.set()
