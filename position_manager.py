"""포지션 상태 관리 모듈 (슬롯 제한 제거 버전)
 - 실시간 Binance 포지션 기준 진입 제한
 - positions.json은 기록용으로만 사용
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from binance_client import client
from utils import cancel_all_orders
from risk_config import MAX_POSITIONS, COOLDOWN_MINUTES

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
    """Binance에서 실시간 오픈 포지션 반환"""
    try:
        all_positions = client.futures_account()['positions']
        open_positions = [p for p in all_positions if float(p['positionAmt']) != 0]
        return open_positions
    except Exception as e:
        logging.error(f"[오류] 실시간 포지션 조회 실패: {e}")
        return []

def add_position(position: Dict[str, Any]) -> None:
    pos = _load_positions()
    pos.append(position)
    _save()

def remove_position(position: Dict[str, Any]) -> None:
    pos = _load_positions()
    try:
        pos.remove(position)
        _save()
    except ValueError:
        pass

def is_duplicate(symbol: str, strategy_name: str) -> bool:
    for p in _load_positions():
        if p["symbol"] == symbol and p["strategy"] == strategy_name:
            return True
    return False

def is_in_cooldown(symbol: str, strategy_name: str) -> bool:
    now = datetime.utcnow()
    for p in _load_positions():
        if p["symbol"] == symbol and p["strategy"] == strategy_name and "entry_time" in p:
            try:
                entered = datetime.fromisoformat(p["entry_time"])
                if now - entered < timedelta(minutes=COOLDOWN_MINUTES):
                    return True
            except Exception as e:
                logging.warning("entry_time 파싱 오류: %s", e)
    return False

def can_enter(strategy_name: str) -> bool:
    """Binance 실시간 포지션 수 기준으로 진입 가능 여부 판단"""
    try:
        positions = get_positions()
        return len(positions) < MAX_POSITIONS
    except Exception as e:
        logging.error(f"[오류] 진입 가능 여부 판단 실패: {e}")
        return False

def start_order_cleanup_loop(symbol_list: List[str]):
    """10초 간격으로 포지션이 없는 심볼의 주문 자동 정리"""
    import threading, time
    def loop():
        while True:
            try:
                open_symbols = {p['symbol'] for p in get_positions()}
                for symbol in symbol_list:
                    if symbol not in open_symbols:
                        cancel_all_orders(symbol)
            except Exception as e:
                logging.error(f"[오류] 주문 정리 루프 실패: {e}")
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True)
    t.start()

def load_positions() -> List[Dict[str, Any]]:
    return _load_positions()