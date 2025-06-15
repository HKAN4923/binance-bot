from position_manager import open_positions, MAX_POSITION_COUNT

def summarize_trades():
    try:
        with open("trades.log", "r") as f:
            lines = f.readlines()
        print(f"총 트레이드 수: {len(lines)}")
        wins = sum(1 for line in lines if "'reason': 'TP'" in line)
        losses = sum(1 for line in lines if "'reason': 'SL'" in line)
        print(f"승: {wins}, 패: {losses}, 승률: {wins / max(1, wins + losses) * 100:.1f}%")
    except FileNotFoundError:
        print("트레이드 로그 없음")

def print_open_positions():
    pos_count = len(open_positions)
    print(f"분석중...({pos_count}/{MAX_POSITION_COUNT})")
    if pos_count > 0:
        for sym, pos in open_positions.items():
            print(f"{sym}: {pos['side']} @ {pos['entry_price']} [{pos['strategy']}]")