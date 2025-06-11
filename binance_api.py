# binance_api.py
"""
Binance Futures REST API wrapper
- send_signed_request: 서명된 요청 전송
- public_request: 퍼블릭 엔드포인트 요청
- get_klines: 캔들스틱(klines) 데이터 조회
- place_market_order: 시장가 주문 (FULL 응답)
- place_market_exit: 청산 주문
- get_price: 현재가 조회
- get_account_info: 계정 정보 조회
- get_position: 특정 심볼 포지션 조회
- get_balance: USDT 잔고 조회
"""
import os
import time
import hmac
import hashlib
import requests
from requests.exceptions import HTTPError
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://fapi.binance.com"

+def get_server_time() -> int:
+    """바이낸스 서버 시간(ms) 조회"""
+    url = BASE_URL + "/fapi/v1/time"
+    resp = requests.get(url)
+    resp.raise_for_status()
+    return resp.json()["serverTime"]
+
+def _get_timestamp_ms():
+    """서버 시간 기준 timestamp(ms) 반환 (동기화)"""
+    try:
+        return get_server_time()
+    except Exception:
+        # 서버 조회 실패 시 로컬 시간 fallback
+        return int(time.time() * 1000)


def _sign_payload(params: dict) -> dict:
    """
    HMAC SHA256 서명 생성 후 payload에 signature를 추가
    """
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
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
     params.update({
+        "timestamp": _get_timestamp_ms(),
+        "recvWindow": 5000
+    })
    
    signed_params = _sign_payload(params)
    headers = {"X-MBX-APIKEY": API_KEY}
    url = BASE_URL + endpoint
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


def get_klines(symbol: str, interval: str, limit: int = 500) -> list:
    """
    과거 캔들스틱(klines) 데이터 조회
    - symbol: 거래쌍 (예: "BTCUSDT")
    - interval: 캔들 간격 (예: "1h", "15m")
    - limit: 가져올 데이터 개수 (최대 1000)
    """
    return public_request(
        "/fapi/v1/klines",
        {"symbol": symbol, "interval": interval, "limit": limit}
    )


def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """
    시장가 주문
    - newOrderRespType="FULL" 로 체결 정보(fills) 포함 요청
    """
    try:
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
    except HTTPError as e:
        # 에러 메시지 JSON 파싱 시도
        try:
            err = e.response.json()
        except Exception:
            err = {"error": str(e)}
        print(f"[Order Error] symbol={symbol}, side={side}, qty={quantity} → {err}")
        return err


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


def get_balance() -> float:
    """
    USDT Futures 계정 잔고(availableBalance) 조회
    """
    account = get_account_info()
    for asset in account.get("assets", []):
        if asset.get("asset") == "USDT":
            return float(asset.get("availableBalance", 0.0))
    return 0.0
