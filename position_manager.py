# 파일명: position_manager.py
# 라쉬케 4 - 포지션 상태 관리 전용 모듈
# 각 전략의 진입/청산, 모니터링 등에서 사용됩니다.

import time
from collections import defaultdict

# 메모리 기반 포지션 저장소
_positions = defaultdict(dict)

def can_enter(symbol: str, strategy: str) -> bool:
    """
    동일 심볼 + 전략으로 이미 포지션이 존재하면 진입 금지
    """
    if symbol in _positions:
        if _positions[symbol].get("strategy") == strategy:
            return False
    return True


def add_position(symbol: str, direction: str, entry_price: float, qty: float, strategy: str) -> None:
    """
    포지션 등록
    """
    _positions[symbol] = {
        "symbol": symbol,
        "side": direction,
        "entry_price": entry_price,
        "qty": qty,
        "strategy": strategy,
        "entry_time": time.time()
    }


def remove_position(symbol: str) -> None:
    """
    포지션 제거
    """
    if symbol in _positions:
        del _positions[symbol]


def get_open_positions() -> dict:
    """
    전체 보유 중인 포지션 딕셔너리 리턴
    """
    return dict(_positions)


def get_position(symbol: str) -> dict:
    """
    특정 심볼 포지션 정보 리턴
    """
    return _positions.get(symbol, {})
