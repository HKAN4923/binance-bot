# trade_summary.py

import os
import json
import threading
import time
from datetime import datetime
from collections import defaultdict

import matplotlib.pyplot as plt

from config import SUMMARY_INTERVAL_SEC, DATE_FORMAT
from telegram_bot import send_message, send_photo

# 거래 내역 저장 파일
TRADE_HISTORY_FILE = "trade_history.json"


def _load_history() -> list:
    """기록된 거래 내역 불러오기"""
    if not os.path.isfile(TRADE_HISTORY_FILE):
        with open(TRADE_HISTORY_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(TRADE_HISTORY_FILE, "r") as f:
        return json.load(f)


def record_trade(position: dict, exit_price: str, reason: str):
    """
    종료된 포지션을 거래 내역에 기록합니다.
    PnL 계산 후 JSON 파일에 append.
    """
    history = _load_history()

    entry_price = float(position["entry_price"])
    qty         = float(position["quantity"])
    exit_price_f= float(exit_price)
    side        = position["side"]

    # PnL 계산 (BUY: (exit-entry)*qty, SELL: (entry-exit)*qty)
    pnl = (exit_price_f - entry_price) * qty if side == "BUY" else (entry_price - exit_price_f) * qty

    record = {
        "strategy":    position["strategy"],
        "symbol":      position["symbol"],
        "side":        side,
        "entry_price": entry_price,
        "exit_price":  exit_price_f,
        "quantity":    qty,
        "pnl":         pnl,
        "reason":      reason,
        "entry_time":  position["entry_time"],
        "exit_time":   datetime.utcnow().strftime(DATE_FORMAT),
    }

    history.append(record)
    with open(TRADE_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def send_summary():
    """
    누적 손익을 전략별로 집계하여 텔레그램으로 전송합니다.
    간단한 막대차트도 함께 전송합니다.
    """
    history = _load_history()
    if not history:
        send_message("📊 누적 손익 내역이 없습니다.")
        return

    strat_pnl = defaultdict(float)
    for rec in history:
        strat_pnl[rec["strategy"]] += rec["pnl"]

    total_pnl = sum(strat_pnl.values())

    # 메시지 구성
    lines = ["📊 누적 손익 요약"]
    for strat, pnl in strat_pnl.items():
        lines.append(f"- {strat}: {pnl:.4f} USDT")
    lines.append(f"전체: {total_pnl:.4f} USDT")
    send_message("\n".join(lines))

    # 차트 생성 및 전송
    strategies = list(strat_pnl.keys())
    pnls       = [strat_pnl[s] for s in strategies]

    plt.figure()
    plt.bar(strategies, pnls)
    plt.title("전략별 누적 PnL")
    plt.ylabel("USDT")
    chart_path = "pnl_summary.png"
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    send_photo(chart_path)


def _summary_scheduler():
    """
    SUMMARY_INTERVAL_SEC 간격으로 자동으로 요약을 전송하는 스레드 함수입니다.
    """
    while True:
        time.sleep(SUMMARY_INTERVAL_SEC)
        send_summary()


def start_summary_scheduler():
    """
    데몬 스레드로 요약 스케줄러를 시작합니다.
    main.py에서 이 함수를 호출해 주세요.
    """
    thread = threading.Thread(target=_summary_scheduler, daemon=True)
    thread.start()
