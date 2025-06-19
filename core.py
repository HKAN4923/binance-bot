# 파일명: core.py
# 공통 함수 및 클래스를 정의하는 모듈입니다.

from binance_client import (
    create_limit_order,
    place_market_order,
    place_market_exit,
    get_price,
    get_klines,
    create_take_profit,
    create_stop_order,
)

from utils import (
    calculate_order_quantity,
    log_trade,
    summarize_trades,
    get_filtered_top_symbols
)

# 포지션 관련 함수는 utils 또는 여기에 직접 정의되어 있다고 가정
from position_manager import (
    can_enter,
    add_position,
    remove_position,
    get_open_positions,
    get_position
)

from telegram_bot import send_telegram

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
