import time
from typing import Dict
from binance_client import BinanceClient
from telegram_notifier import (
    send_position_alert,
    send_position_close,
    send_error_alert,
)
from config import Config
from rashke_strategies import (
    ATRBreakoutStrategy,
    PreviousDayBreakoutStrategy,
    MovingAveragePullbackStrategy,
)


class Position:
    def __init__(self, symbol, side, qty, entry, sl, tp):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.entry = entry
        self.sl = sl
        self.tp = tp


class RashkeBot:
    def __init__(self):
        self.client = BinanceClient()
        self.strategies = [
            ATRBreakoutStrategy(self.client),
            PreviousDayBreakoutStrategy(self.client),
            MovingAveragePullbackStrategy(self.client),
        ]
        self.symbols = [
            s["symbol"]
            for s in self.client.client.get_ticker_24hr()
            if s["symbol"].endswith("USDT")
        ][:50]
        self.positions: Dict[str, Position] = {}

    def _calc_quantity(self, price: float) -> float:
        balance = self.client.get_account_balance()
        qty = (balance * Config.POSITION_SIZE * Config.LEVERAGE) / price
        return round(qty, 3)

    def open_position(self, symbol: str, signal: Dict):
        qty = self._calc_quantity(signal["entry"])
        if qty <= 0:
            return
        self.client.place_order(
            symbol,
            signal["side"],
            qty,
            stop_loss=signal["sl"],
            take_profit=signal["tp"],
        )
        self.positions[symbol] = Position(
            symbol, signal["side"], qty, signal["entry"], signal["sl"], signal["tp"]
        )
        send_position_alert(symbol, signal["side"], qty, signal["entry"], signal["sl"], signal["tp"])

    def check_positions(self):
        for symbol, pos in list(self.positions.items()):
            mark = float(self.client.client.futures_mark_price(symbol=symbol)["markPrice"])
            if pos.side == "BUY" and (mark <= pos.sl or mark >= pos.tp):
                self.client.close_position(symbol, pos.side, pos.qty)
                send_position_close(symbol, pos.side, pos.qty)
                self.positions.pop(symbol, None)
            elif pos.side == "SELL" and (mark >= pos.sl or mark <= pos.tp):
                self.client.close_position(symbol, pos.side, pos.qty)
                send_position_close(symbol, pos.side, pos.qty)
                self.positions.pop(symbol, None)

    def run(self):
        while True:
            try:
                if len(self.positions) < Config.MAX_POSITIONS:
                    for sym in self.symbols:
                        if sym in self.positions:
                            continue
                        for strat in self.strategies:
                            signal = strat.generate_signal(sym)
                            if signal:
                                self.open_position(sym, signal)
                                break
                        if len(self.positions) >= Config.MAX_POSITIONS:
                            break
                self.check_positions()
                time.sleep(Config.POSITION_CHECK_INTERVAL)
            except Exception as e:
                send_error_alert(str(e))
                time.sleep(Config.POSITION_CHECK_INTERVAL)


if __name__ == "__main__":
    bot = RashkeBot()
    bot.run()
