"""Track trade results and send periodic summaries."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt

import telegram_bot

TRADES_FILE = Path("trades.json")


def _load_trades() -> List[Dict[str, Any]]:
    if TRADES_FILE.exists():
        return json.loads(TRADES_FILE.read_text())
    return []


def add_trade_entry(entry: Dict[str, Any]) -> None:
    """Add a trade entry to the log."""
    trades = _load_trades()
    trades.append(entry)
    TRADES_FILE.write_text(json.dumps(trades, indent=2))


def summarize_by_strategy() -> Dict[str, Any]:
    """Compute win rate and PnL by strategy."""
    trades = _load_trades()
    result: Dict[str, Dict[str, float]] = {}
    for t in trades:
        strat = t["strategy"]
        r = result.setdefault(strat, {"wins": 0, "trades": 0, "pnl": 0.0})
        r["trades"] += 1
        if t.get("pnl", 0) > 0:
            r["wins"] += 1
        r["pnl"] += t.get("pnl", 0)
    for v in result.values():
        v["win_rate"] = v["wins"] / v["trades"] * 100 if v["trades"] else 0
    return result


def generate_equity_curve(path: str) -> None:
    """Generate an equity curve graph from trade history."""
    trades = _load_trades()
    equity = 0
    curve = []
    for t in trades:
        equity += t.get("pnl", 0)
        curve.append(equity)
    plt.figure()
    plt.plot(curve)
    plt.title("Equity Curve")
    plt.xlabel("Trade #")
    plt.ylabel("PnL")
    plt.savefig(path)
    plt.close()


def send_telegram() -> None:
    summary = summarize_by_strategy()
    message_lines = ["Trade Summary"]
    for strat, data in summary.items():
        line = f"[{strat}] WinRate: {data['win_rate']:.1f}% PnL: {data['pnl']:.2f}"
        message_lines.append(line)
    telegram_bot.send_message("\n".join(message_lines))


def send_telegram_photo(path: str) -> None:
    telegram_bot.send_photo(path, "Equity Curve")


def start_summary_scheduler() -> None:
    """Start a periodic summary every 2 hours."""
    import threading
    import time

    def _worker() -> None:
        while True:
            try:
                send_telegram()
                graph_path = "equity.png"
                generate_equity_curve(graph_path)
                send_telegram_photo(graph_path)
            except Exception as exc:  # pragma: no cover - best effort
                logging.error("Summary scheduler error: %s", exc)
            time.sleep(7200)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
