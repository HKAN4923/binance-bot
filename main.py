import time
import threading
from decimal import Decimal, ROUND_DOWN
from typing import Dict

from binance_client import (
    get_account_balance, place_order, close_position,
    get_mark_price, get_open_position_amt, cancel_all_sltp
)
from telegram_notifier import (
    send_telegram, send_position_alert, send_position_close, send_error_alert
)
from config import Config
from strategy import (
    ATRBreakoutStrategy,
    PreviousDayBreakoutStrategy,
    MovingAveragePullbackStrategy,
    check_entry_multi,
    count_entry_signals
)
from utils import to_kst, calculate_qty, get_top_100_volume_symbols, get_ohlcv
from trade_summary import trade_summary

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class Position:
    def __init__(self, symbol, side, qty, entry, sl, tp, reason, method, cnt5, cnt1, rashke):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.entry = entry
        self.sl = sl
        self.tp = tp
        self.reason = reason
        self.method = method
        self.cnt5 = cnt5
        self.cnt1 = cnt1
        self.rashke = rashke


class TradingBot:
    def __init__(self):
        self.strategies = {
            "ATR": ATRBreakoutStrategy(None),
            "PDH": PreviousDayBreakoutStrategy(None),
            "MAP": MovingAveragePullbackStrategy(None),
        }
        self.positions: Dict[str, Position] = {}
        self.last_log = 0

    def calc_qty(self, price: float) -> float:
        bal = get_account_balance()
        qty = (bal * Config.MAX_EXPOSURE * Config.LEVERAGE) / price
        return float(Decimal(qty).quantize(Decimal("1e-3"), rounding=ROUND_DOWN))

    def open_pos(self, pos: Position):
        place_order(
            pos.symbol, pos.side, pos.qty,
            stop_loss=pos.sl, take_profit=pos.tp
        )
        self.positions[pos.symbol] = pos
        send_position_alert(
            pos.symbol, pos.side, pos.qty,
            pos.entry, pos.sl, pos.tp
        )
        send_telegram(
            f"<b>▶ ENTRY</b>\n"
            f"{pos.symbol} {pos.side}\n"
            f"Reason: {pos.reason}\nMethod: {pos.method}\n"
            f"5m:{pos.cnt5} 1m:{pos.cnt1} Rashke:{pos.rashke}"
        )

    def close_pos(self, symbol: str):
        pos = self.positions.pop(symbol)
        mark = Decimal(str(get_mark_price(symbol)))
        pnl = (mark - pos.entry) * Decimal(str(pos.qty)) if pos.side=="BUY" else (pos.entry - mark) * Decimal(str(pos.qty))
        close_position(symbol, pos.side, pos.qty)
        trade_summary.record(float(pnl))
        res = "WIN" if pnl>0 else "LOSS"
        send_position_close(symbol, pos.side, pos.qty)
        send_telegram(
            f"<b>▶ CLOSE</b>\n{symbol} {pos.side}\n"
            f"PnL: {pnl:.2f} USDT ({float(pnl/ (pos.entry*pos.qty)*100):.2f}%)\n"
            f"Result: {res}\n"
            f"W:{trade_summary.wins} L:{trade_summary.losses} WR:{trade_summary.get_win_rate():.2f}%\n"
            f"CumPnL: {trade_summary.get_total_pnl():.2f} USDT"
        )

    def run(self):
        while True:
            now = time.time()
            if now - self.last_log >= 10:
                print(f"{time.strftime('%H:%M:%S')} 분석중.. ({len(self.positions)}/{Config.MAX_POSITIONS})", flush=True)
                self.last_log = now

            # 진입
            if len(self.positions) < Config.MAX_POSITIONS:
                syms = get_top_100_volume_symbols()
                for sym in syms:
                    if sym in self.positions: continue
                    df1 = get_ohlcv(sym, "1m", 50); df5 = get_ohlcv(sym, "5m", 50)
                    cnt1 = sum(count_entry_signals(df1)) if df1 is not None else 0
                    cnt5 = sum(count_entry_signals(df5)) if df5 is not None else 0
                    my_sig = check_entry_multi(df1, Config.PRIMARY_THRESHOLD)
                    rashke_sig = None; ras_m = ""
                    for k,s in self.strategies.items():
                        sig = s.generate_signal(sym)
                        if sig:
                            rashke_sig, ras_m = sig, k
                            break

                    if my_sig:
                        price = Decimal(str(df1["close"].iloc[-1]))
                        sl = float(price * (1-Config.SL_RATIO)) if my_sig=="long" else float(price*(1+Config.SL_RATIO))
                        tp = float(price * (1+Config.TP_RATIO)) if my_sig=="long" else float(price*(1-Config.TP_RATIO))
                        pos = Position(sym, "BUY" if my_sig=="long" else "SELL",
                                       self.calc_qty(float(price)), price,
                                       Decimal(str(sl)), Decimal(str(tp)),
                                       "내로직", "Multi", cnt5, cnt1, "")
                        self.open_pos(pos)
                    elif rashke_sig:
                        entry,sl,tp = map(Decimal, (rashke_sig["entry"], rashke_sig["sl"], rashke_sig["tp"]))
                        side = rashke_sig["side"]
                        pos = Position(sym, side, self.calc_qty(float(entry)), entry, sl, tp,
                                       "라쉬케", ras_m, cnt5, cnt1, ras_m)
                        self.open_pos(pos)

                    if len(self.positions)>=Config.MAX_POSITIONS: break

            # 청산
            for sym in list(self.positions):
                pos = self.positions[sym]
                mark = Decimal(str(get_mark_price(sym)))
                if (pos.side=="BUY" and (mark<=pos.sl or mark>=pos.tp)) or \
                   (pos.side=="SELL" and (mark>=pos.sl or mark<=pos.tp)):
                    self.close_pos(sym)

            time.sleep(Config.ANALYSIS_INTERVAL_SEC)


if __name__=="__main__":
    bot = TradingBot()
    bot.run()
