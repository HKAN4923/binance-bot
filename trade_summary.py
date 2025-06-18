# trade_summary.py
import json
import os
from collections import defaultdict
from utils import now_string

LOG_FILE = "trade_log.json"

def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def summarize_trades():
    logs = load_logs()
    summary = defaultdict(lambda: {"win": 0, "loss": 0, "pl": 0.0})
    total_win = total_loss = 0

    for log in logs:
        if log["status"] != "exit":
            continue
        strategy = log["strategy"]
        entry = log["entry_price"]
        exit_ = log["exit_price"]
        size = log["position_size"]
        side = log["side"]

        pl = (exit_ - entry) * size if side == "long" else (entry - exit_) * size
        summary[strategy]["pl"] += pl
        if pl >= 0:
            summary[strategy]["win"] += 1
            total_win += 1
        else:
            summary[strategy]["loss"] += 1
            total_loss += 1

    msg = f"📊 누적 요약 ({now_string()})\n"
    for strategy, stat in summary.items():
        total = stat["win"] + stat["loss"]
        winrate = (stat["win"] / total) * 100 if total > 0 else 0
        msg += (
            f"{strategy.upper()} ➤ {stat['win']}승 {stat['loss']}패 "
            f"(승률: {winrate:.1f}%) / 누적손익: {stat['pl']:.2f}\n"
        )

    total = total_win + total_loss
    total_winrate = (total_win / total) * 100 if total > 0 else 0
    total_pl = sum(stat["pl"] for stat in summary.values())
    msg += f"📈 전체 ➤ {total_win}승 {total_loss}패 (승률: {total_winrate:.1f}%) / 누적손익: {total_pl:.2f}"
    return msg