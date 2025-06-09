# trade_summary.py
class TradeSummary:
    def __init__(self):
        self.wins = 0
        self.losses = 0

    def record(self, pnl: float):
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1

    def __str__(self):
        total = self.wins + self.losses
        win_rate = (self.wins / total * 100) if total > 0 else 0
        return f"Wins: {self.wins}, Losses: {self.losses}, Win Rate: {win_rate:.2f}%"