# 파일명: core.py
# 공통 함수 및 클래스를 정의하는 모듈입니다.
# 이 파일의 함수명을 기준으로 다른 모듈이 import합니다.

# Binance API 주문 및 데이터 조회
from binance_client import (
    create_limit_order,
    place_market_order,
    place_market_exit,
)
from binance_api import (
    get_price,
    get_klines,
    create_take_profit,
    create_stop_order,
)

# 유틸리티 함수
from utils import (
    calculate_order_quantity,
    log_trade,
    summarize_trades,
    get_filtered_top_symbols
)

# 포지션 관리
from position_manager import (
    can_enter,
    add_position,
    remove_position,
    get_open_positions,
    get_position
)

# 알림
from telegram_bot import send_telegram

# 이 모듈에서 공개하는 API 목록
__all__ = [
    "create_limit_order",
    "place_market_order",
    "place_market_exit",
    "get_price",
    "get_klines",
    "create_take_profit",
    "create_stop_order",
    "calculate_order_quantity",
    "log_trade",
    "summarize_trades",
    "get_filtered_top_symbols",
    "can_enter",
    "add_position",
    "remove_position",
    "get_open_positions",
    "get_position",
    "send_telegram"
]
