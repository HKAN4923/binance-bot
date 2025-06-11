# binance_api.py
"""
Binance Futures REST API wrapper
- send_signed_request: 서명된 요청 전송
- public_request: 퍼블릭 엔드포인트 요청
- place_market_order: 시장가 주문 (FULL 응답)
- place_market_exit: 청산 주문
- get_price: 현재가 조회
- get_account_info: 계정 정보 조회
- get_position: 특정 심볼 포지션 조회
"""
import os
import time
import hmac
import hashlib
import requests

from dotenv import load_dotenv

# .env에서 API 키 및 시크릿 불러오기
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")
BASE_URL = "https://fapi.binance.com"


def _get_timestamp_ms():
    """현재 시간(밀리초) 반환"""
    return int(time.time() * 1000)


def _sign_payload(params: dict) -> dict:
    """
    HMAC SHA256 서명 생성 후 payload에 signature를 추가
    """
    # 파라미터 정렬 및 쿼리 스트링 생성
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    # 시그니처 계산
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    return params


def send_signed_request(http_method: str, endpoint: str, params: dict) -> dict:
    """
    서명된 요청을 바이낸스 선물 API로 전송
    - http_method: "GET", "POST" 등
    - endpoint: 예) "/fapi/v1/order"
    - params: 요청 파라미터
    """
    # 타임스탬프 추가
    params.update({"timestamp": _get_timestamp_ms()})
    # 시그니처 생성
    signed_params = _sign_payload(params)
    headers = {"X-MBX-APIKEY": API_KEY}
    url = BASE_URL + endpoint
    # 요청 전송
    if http_method.upper() == "GET":
        response = requests.get(url, headers=headers, params=signed_params)
    else:
        response = requests.request(http_method.upper(), url, headers=headers, params=signed_params)
    response.raise_for_status()
    return response.json()


def public_request(endpoint: str, params: dict = None) -> dict:
    """
    퍼블릭 엔드포인트 GET 요청
    - endpoint: 예) "/fapi/v1/ticker/price"
    - params: 조회 파라미터
    """
    url = BASE_URL + endpoint
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """
    시장가 주문
    - newOrderRespType="FULL" 로 체결 정보(fills) 포함 요청
    """
    return send_signed_request(
        "POST",
        "/fapi/v1/order",
        {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
            "newOrderRespType": "FULL"
        }
    )


def place_market_exit(symbol: str, side: str, quantity: float) -> dict:
    """
    청산(시장가) 주문
    - 진입 주문과 동일하게 FULL 응답 요청
    """
    return place_market_order(symbol, side, quantity)


def get_price(symbol: str) -> float:
    """
    현재가 조회
    """
    data = public_request(
        "/fapi/v1/ticker/price",
        {"symbol": symbol}
    )
    return float(data.get("price", 0))


def get_account_info() -> dict:
    """
    계정 정보(잔고, 포지션 등) 조회
    """
    return send_signed_request(
        "GET",
        "/fapi/v2/account",
        {}
    )


def get_position(symbol: str) -> dict:
    """
    특정 심볼의 포지션 정보 조회
    """
    account = get_account_info()
    for pos in account.get("positions", []):
        if pos.get("symbol") == symbol:
            return pos
    return {}
