# trade_summary.py

# ✅ 승률 기록 및 통계 클래스
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

# ✅ 인스턴스 생성 (외부에서 import 시 바로 사용 가능)
trade_summary = TradeSummary()