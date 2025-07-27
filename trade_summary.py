"""거래 요약 및 알림 모듈"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import telegram_bot

TRADES_FILE = Path("trades.json")


def _load_trades() -> List[Dict[str, Any]]:
    if TRADES_FILE.exists():
        return json.loads(TRADES_FILE.read_text())
    return []


def add_trade_entry(entry: Dict[str, Any]) -> None:
    """거래 기록 저장"""
    trades = _load_trades()
    trades.append(entry)
    TRADES_FILE.write_text(json.dumps(trades, indent=2))
    logging.info(f"[기록] {entry['symbol']} 거래 저장됨 (PnL: {entry.get('pnl', 0):.2f})")


def summarize_by_strategy() -> Dict[str, Any]:
    """전략별 손익 및 승률 계산"""
    trades = _load_trades()
    summary: Dict[str, Dict[str, float]] = {}

    for t in trades:
        strat = t["strategy"]
        result = summary.setdefault(strat, {"wins": 0, "trades": 0, "pnl": 0.0})
        result["trades"] += 1
        result["pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            result["wins"] += 1

    for stat in summary.values():
        stat["win_rate"] = (
            stat["wins"] / stat["trades"] * 100 if stat["trades"] else 0.0
        )

    return summary


def send_telegram() -> None:
    """전략별 요약 메시지 전송"""
    summary = summarize_by_strategy()
    lines = [f"📊 전략별 누적 요약 "]

    total_pnl = 0
    total_wins = 0
    total_trades = 0

    for strat, data in summary.items():
        lines.append(
            f"[{strat}] 진입: {data['trades']}회 | 승률: {data['win_rate']:.1f}% | 손익: {data['pnl']:.2f} USDT"
        )
        total_pnl += data["pnl"]
        total_wins += data["wins"]
        total_trades += data["trades"]

    total_win_rate = total_wins / total_trades * 100 if total_trades else 0.0
    lines.append(f"\n📈 전체 손익: {total_pnl:.2f} USDT")
    lines.append(f"🎯 전체 승률: {total_win_rate:.1f}%")

    telegram_bot.send_message("\n".join(lines))


def start_summary_scheduler() -> None:
    """2시간마다 자동 요약 스케줄 시작 (그래프 제외)"""
    def _worker():
        while True:
            try:
                send_telegram()
            except Exception as e:
                logging.error(f"[오류] 요약 전송 실패: {e}")
            time.sleep(2 * 60 * 60)  # 2시간

    threading.Thread(target=_worker, daemon=True).start()


def send_trade_file_daily():
    """trades.json 파일을 하루 1회 텔레그램으로 전송"""
    try:
        with open("trades.json", "rb") as f:
            telegram_bot.send_document(f, filename="trades.json")
        logging.info("[전송] trades.json 파일 텔레그램 전송 완료")
    except Exception as e:
        logging.error(f"[오류] 거래 로그 전송 실패: {e}")


def start_daily_file_sender():
    """매일 자정에 trades.json 파일 텔레그램으로 전송"""
    def _worker():
        while True:
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                send_trade_file_daily()
                time.sleep(61)  # 중복 방지
            time.sleep(30)  # 30초마다 확인

    threading.Thread(target=_worker, daemon=True).start()
