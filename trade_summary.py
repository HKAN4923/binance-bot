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

    def get_win_rate(self) -> float:
        total = self.wins + self.losses
        return (self.wins / total * 100) if total > 0 else 0.0

    def get_total_pnl(self) -> float:
        return self.total_pnl

trade_summary = TradeSummary()
