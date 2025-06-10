class TradeSummary:
    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

    def record(self, pnl: float):
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl += pnl

    def get_summary_message(self):
        total = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0
        msg = (
            f"📊 Trade Summary:\n"
            f"Wins: {self.wins}\n"
            f"Losses: {self.losses}\n"
            f"Win Rate: {win_rate:.2f}%\n"
            f"Total PnL: {self.total_pnl:.2f} USDT"
        )
        return msg

trade_summary = TradeSummary()
