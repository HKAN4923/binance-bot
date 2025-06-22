# position_manager.py

import json
import os
import logging
from typing import List, Dict
from config import MAX_POSITIONS

# 포지션을 저장할 파일
POSITIONS_FILE = "positions.json"


def _load_positions() -> List[Dict]:
    if not os.path.isfile(POSITIONS_FILE):
        with open(POSITIONS_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[포지션 로드 오류] {e}")
        return []


def _save_positions(positions: List[Dict]):
    try:
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions, f, indent=2)
    except Exception as e:
        logging.error(f"[포지션 저장 오류] {e}")


# 메모리 로드
_positions: List[Dict] = _load_positions()


def get_positions() -> List[Dict]:
    """현재 보유 중인 포지션 목록 반환"""
    return _positions


def can_enter() -> bool:
    """최대 포지션 수(MAX_POSITIONS) 미만일 때만 진입 허용"""
    return len(_positions) < MAX_POSITIONS


def add_position(position: Dict):
    """
    신규 포지션 등록.
    최대치 초과 시 로깅만 하고 등록하지 않습니다.
    """
    if not can_enter():
        logging.error(f"[포지션 초과] 최대 포지션 수({MAX_POSITIONS}) 도달, 등록 불가")
        return
    _positions.append(position)
    _save_positions(_positions)


def remove_position(position: Dict):
    """
    포지션 제거.
    symbol, entry_time, strategy가 모두 일치하는 항목을 삭제합니다.
    """
    global _positions
    _positions = [
        p for p in _positions
        if not (
            p.get("symbol") == position.get("symbol")
            and p.get("entry_time") == position.get("entry_time")
            and p.get("strategy") == position.get("strategy")
        )
    ]
    _save_positions(_positions)
