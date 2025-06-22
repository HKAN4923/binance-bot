"""포지션 상태 관리 모듈"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from risk_config import MAX_POSITIONS, RESERVED_SLOTS, COOLDOWN_MINUTES

POSITIONS_FILE = Path("positions.json")
_positions_cache: List[Dict[str, Any]] | None = None


def _load_positions() -> List[Dict[str, Any]]:
    global _positions_cache
    if _positions_cache is None:
        if POSITIONS_FILE.exists():
            _positions_cache = json.loads(POSITIONS_FILE.read_text())
        else:
            _positions_cache = []
    return _positions_cache


def _save() -> None:
    if _positions_cache is not None:
        POSITIONS_FILE.write_text(json.dumps(_positions_cache, indent=2))


def get_positions() -> List[Dict[str, Any]]:
    """현재 열려 있는 포지션 반환"""
    return list(_load_positions())


def add_position(position: Dict[str, Any]) -> None:
    """포지션 등록 및 저장"""
    pos = _load_positions()
    pos.append(position)
    _save()


def remove_position(position: Dict[str, Any]) -> None:
    """포지션 제거"""
    pos = _load_positions()
    try:
        pos.remove(position)
        _save()
    except ValueError:
        pass


def is_duplicate(symbol: str, strategy_name: str) -> bool:
    """같은 심볼+전략 중복 진입 여부 확인"""
    for p in _load_positions():
        if p["symbol"] == symbol and p["strategy"] == strategy_name:
            return True
    return False


def is_in_cooldown(symbol: str, strategy_name: str) -> bool:
    """최근 진입한 포지션이 30분 이내인지 확인"""
    now = datetime.utcnow()
    for p in _load_positions():
        if (
            p["symbol"] == symbol
            and p["strategy"] == strategy_name
            and "entry_time" in p
        ):
            try:
                entered = datetime.fromisoformat(p["entry_time"])
                if now - entered < timedelta(minutes=COOLDOWN_MINUTES):
                    return True
            except Exception as e:
                logging.warning("entry_time 파싱 오류: %s", e)
    return False


def can_enter(strategy_name: str) -> bool:
    """현재 전략이 진입 가능한 상태인지 확인"""

    pos = _load_positions()
    if len(pos) >= MAX_POSITIONS:
        return False

    # ORB/NR7 우선 전략은 RESERVED 슬롯 보장
    if strategy_name.upper() in {"ORB", "NR7"}:
        return True

    # EMA/PULLBACK은 시간대에 따라 제한 적용됨
    non_reserved = [p for p in pos if p["strategy"] not in {"ORB", "NR7"}]
    if len(non_reserved) >= MAX_POSITIONS - RESERVED_SLOTS:
        return False

    return True
