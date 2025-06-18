# trade_summary.py - 포지션 상태를 터미널과 텔레그램으로 출력하는 유틸

from position_manager import get_open_positions
from telegram_bot import send_telegram

# 포지션 상태 출력 (터미널 + 텔레그램)
def print_open_positions():
    positions = get_open_positions()

    if not positions:
        print("📭 현재 보유 중인 포지션 없음")
        return

    print("📌 현재 보유 포지션:")
    lines = []
    for sym, pos in positions.items():
        info = f"{sym} | {pos['side']} | 진입가: {pos['entry_price']} | 수량: {pos['qty']} | 전략: {pos['strategy']}"
        print(info)
        lines.append(info)

    send_telegram("📌 현재 보유 포지션:\n" + "\n".join(lines))
