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

class PositionMonitor(threading.Thread):
    """
    포지션별 긴급 탈출 및 반전 신호 감시를 담당합니다.
    - 1초 간격으로 다음을 체크:
      1) 긴급 손실(Deep Drawdown): EMERGENCY_PERIOD 내 잔고가 EMERGENCY_DROP_PERCENT 이상 하락 시,
         모든 포지션 청산 및 봇 중단.
      2) 보유시간 초과: MAX_TRADE_DURATION(초) 이상 보유 시 해당 심볼 전량 청산.
      3) 반전 신호 감지: 진입 후 60초가 지난 포지션에 대해 1분봉 반전 신호(confidence ≥ 0.8)가 발생하면 청산.
    """

    def __init__(self, positions, positions_lock, trade_log, trade_log_lock, close_callback):
        super().__init__()
        self.daemon = True
        self.positions = positions
        self.positions_lock = positions_lock
        self.trade_log = trade_log
        self.trade_log_lock = trade_log_lock
        self.close_callback = close_callback

        # 잔고 기록을 보관하기 위한 deque (최대 EMERGENCY_PERIOD 길이)
        self.balance_history = deque()

        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                # ─────────────── 긴급 손실(Deep Drawdown) 체크 ───────────────
                current_balance = Decimal(str(get_balance()))
                now = time.time()
                # (timestamp, balance) 형태로 저장
                self.balance_history.append((now, current_balance))

                # EMERGENCY_PERIOD 초 이전 데이터는 제거
                while self.balance_history and (now - self.balance_history[0][0]) > EMERGENCY_PERIOD:
                    self.balance_history.popleft()

                # deque에 보관된 가장 오래된 잔고와 현재 잔고를 비교
                if len(self.balance_history) >= 2:
                    oldest_ts, oldest_bal = self.balance_history[0]
                    # 손실률 계산
                    drawdown = (oldest_bal - current_balance) / oldest_bal if oldest_bal > 0 else Decimal("0")
                    if drawdown >= EMERGENCY_DROP_PERCENT:
                        # 모든 포지션 청산 및 봇 중단
                        logging.error(f"[긴급 손실] {drawdown * 100:.2f}% 손실 발생 → 모든 포지션 청산 후 프로그램 종료")
                        send_telegram(f"<b>🚨 긴급 손실 {drawdown * 100:.2f}% 발생</b>\n모든 포지션을 청산하고 봇을 중단합니다.")
                        with self.positions_lock:
                            symbols = list(self.positions.keys())
                        for symbol in symbols:
                            cancel_all_orders_for_symbol(symbol)
                            with self.positions_lock:
                                self.positions.pop(symbol, None)
                        sys.exit(1)

                # ─────────────── 포지션별 반복 체크 ───────────────
                with self.positions_lock:
                    current_positions = dict(self.positions)

                for symbol, pos in current_positions.items():
                    try:
                        side = pos['side']                # "long" 또는 "short"
                        entry_price = pos['entry_price']  # Decimal
                        start_time = pos['start_time']    # 진입 시각 (timestamp)
                        quantity = pos['quantity']        # Decimal

                        # 1) 보유시간 초과 체크
                        elapsed = time.time() - start_time
                        if elapsed >= MAX_TRADE_DURATION:
                            # 전량 청산
                            cancel_all_orders_for_symbol(symbol)
                            # 시장가 전량 청산
                            from binance_client import create_market_order, get_open_position_amt
                            actual_amt = get_open_position_amt(symbol)
                            if actual_amt > 0:
                                create_market_order(symbol,
                                                     "SELL" if side == "BUY" else "BUY",
                                                     float(actual_amt),
                                                     reduceOnly=True)
                            with self.positions_lock:
                                self.positions.pop(symbol, None)
                            # 청산 콜백 호출 (PnL 정보는 close_callback 내부에서 계산)
                            # trade_log는 PositionMonitor가 아닌 close_callback을 통해 업데이트됨
                            continue

                        # 2) 반전 신호 체크 (진입 후 60초 지난 경우에만)
                        if time.time() - start_time > 60:
                            # 1분봉 데이터 조회
                            df1m = get_ohlcv(symbol, '1m', limit=50)
                            if df1m is not None and len(df1m) >= 50:
                                sig_info = check_entry_with_confidence(df1m)
                                # 'side' 필드가 있고 기존 포지션과 반대이며 확신도 ≥ 0.8인 경우
                                if sig_info.get('side') and sig_info['side'] != pos.get('side') and sig_info.get('confidence', 0) >= 0.8:
                                    logging.info(f"{symbol} 반전 신호 감지(확신도 {sig_info['confidence']:.2f}) → 전량 청산")
                                    send_telegram(f"🔁 반대 신호 감지: {symbol} 청산합니다.")
                                    cancel_all_orders_for_symbol(symbol)
                                    from binance_client import create_market_order, get_open_position_amt
                                    actual_amt = get_open_position_amt(symbol)
                                    if actual_amt > 0:
                                        create_market_order(symbol,
                                                             "SELL" if side == "BUY" else "BUY",
                                                             float(actual_amt),
                                                             reduceOnly=True)
                                    with self.positions_lock:
                                        self.positions.pop(symbol, None)
                                    continue

                        # # PnL 기반 손절/익절 등은 main.py의 monitor_position()에서 담당하므로 여기서 추가 처리하지 않음

                    except Exception as e:
                        logging.error(f"[{symbol} 모니터링 오류] {e}")
                        continue

                time.sleep(1)

            except Exception as e:
                logging.error(f"[PositionMonitor 오류] {e}")
                time.sleep(1)
