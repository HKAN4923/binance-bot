import threading
import time
import logging
import weakref  # 메모리 관리 개선
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
        self.balance_history = deque(maxlen=120)  # 10분(120*5초) 기록 보관
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                # 잔고 드로우다운 체크 (5초 주기)
                current_balance = Decimal(str(get_balance()))
                now = time.time()
                self.balance_history.append((now, current_balance))
                
                # 오래된 데이터 제거
                while self.balance_history and (now - self.balance_history[0][0]) > EMERGENCY_PERIOD:
                    self.balance_history.popleft()
                
                # 긴급 손실 체크
                if len(self.balance_history) >= 2:
                    oldest_ts, oldest_bal = self.balance_history[0]
                    drawdown = (oldest_bal - current_balance) / oldest_bal if oldest_bal > 0 else Decimal("0")
                    
                    if drawdown >= EMERGENCY_DROP_PERCENT:
                        logging.error(f"[긴급 손실] {drawdown * 100:.2f}% 손실 → 청산 후 종료")
                        send_telegram(f"<b>🚨 긴급 손실 {drawdown * 100:.2f}% 발생</b>\n포지션 전량 청산, 봇 종료")
                        
                        with self.positions_lock:
                            symbols = list(self.positions.keys())
                        
                        for symbol in symbols:
                            cancel_all_orders_for_symbol(symbol)
                            amt = get_open_position_amt(symbol)
                            if amt > 0:
                                create_market_order(symbol, "SELL", amt, reduceOnly=True)
                            with self.positions_lock:
                                if symbol in self.positions:
                                    self.positions.pop(symbol, None)
                        return

                # 메모리 누수 방지 (약한 참조 사용)
                positions_ref = weakref.ref(self.positions)
                
                # 포지션별 모니터링
                with self.positions_lock:
                    current_positions = dict(positions_ref() or {})
                
                for symbol, pos in current_positions.items():
                    side = pos['side']
                    start_time = pos['start_time']

                    # 보유시간 초과 체크
                    if time.time() - start_time >= MAX_TRADE_DURATION:
                        logging.info(f"{symbol} 최대 보유시간 초과 → 청산")
                        cancel_all_orders_for_symbol(symbol)
                        amt = get_open_position_amt(symbol)
                        if amt > 0:
                            create_market_order(
                                symbol, 
                                "SELL" if side == "long" else "BUY", 
                                amt, 
                                reduceOnly=True
                            )
                        with self.positions_lock:
                            if symbol in self.positions:
                                self.positions.pop(symbol, None)
                        continue

                    # 반전 신호 감시 (60초 이후부터)
                    if time.time() - start_time > 60:
                        df1 = get_ohlcv(symbol, '1m', limit=50)
                        if df1 is not None and len(df1) >= 50:
                            if check_reversal_multi(df1, threshold=3):  # 2 → 3 (더 엄격)
                                logging.info(f"{symbol} 다중 반전 신호 감지 → 청산")
                                send_telegram(f"🔁 반전 신호 감지: {symbol} 청산")
                                cancel_all_orders_for_symbol(symbol)
                                amt = get_open_position_amt(symbol)
                                if amt > 0:
                                    create_market_order(
                                        symbol,
                                        "SELL" if side == "long" else "BUY",
                                        amt,
                                        reduceOnly=True
                                    )
                                with self.positions_lock:
                                    if symbol in self.positions:
                                        self.positions.pop(symbol, None)
                                continue

                time.sleep(5)
            except Exception as e:
                logging.error(f"[PositionMonitor 오류] {e}")
                time.sleep(5)
