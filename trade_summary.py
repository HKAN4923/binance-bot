# trade_summary.py
from position_manager import get_open_positions
from telegram_bot import send_telegram
from risk_config import MAX_POSITIONS

def print_open_positions():
    positions = get_open_positions()
    count = len(positions)
    print(f"분석중...({count}/{MAX_POSITIONS})")

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
