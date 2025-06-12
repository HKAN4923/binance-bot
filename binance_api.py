# binance_api.py
"""
Binance Futures REST API wrapper
- 서명된 요청 처리 및 주요 엔드포인트 호출 함수 정의
"""



import os
import time
import hmac
import hashlib
import requests
from requests.exceptions import HTTPError
from dotenv import load_dotenv

# ✅ .env 파일 강제 경로 로드 (경로 필요 시 수정)
load_dotenv(dotenv_path="./.env")

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

if not API_SECRET:
    raise ValueError("❌ API_SECRET가 .env에서 로드되지 않았습니다.")

if not isinstance(API_SECRET, str):
    raise TypeError("❌ API_SECRET는 str 타입이어야 합니다.")

# 인코딩은 여기서 수행
API_SECRET = API_SECRET.encode('utf-8')

# ✅ 환경변수 로딩
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# ✅ 디버그 로그 (실제 운영 시 삭제해도 됨)
print(f"[🔑] API_KEY loaded: {bool(API_KEY)}")
print(f"[🔐] API_SECRET loaded: {bool(API_SECRET)}")

# ✅ 필수 키 누락 시 종료
if not API_KEY or not API_SECRET:
    raise ValueError("❌ .env에서 BINANCE_API_KEY 또는 BINANCE_API_SECRET이 누락되었습니다.")

BASE_URL = "https://fapi.binance.com"


def get_server_time() -> int:
    """서버 시간(ms) 동기화"""
    url = BASE_URL + "/fapi/v1/time"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["serverTime"]


def _get_timestamp_ms():
    """서버 시간 또는 로컬 시간 기준 타임스탬프(ms)"""
    try:
        return get_server_time()
    except:
        return int(time.time() * 1000)


def _sign_payload(params: dict) -> dict:
    """파라미터에 HMAC SHA256 서명 추가"""
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    return params


def send_signed_request(http_method: str, endpoint: str, params: dict) -> dict:
    """서명된 Binance API 요청 (Signature invalid 시 1회 재시도)"""
    params.update({
        "timestamp": _get_timestamp_ms(),
        "recvWindow": 5000
    })
    signed_params = _sign_payload(params)
    headers = {"X-MBX-APIKEY": API_KEY}
    url = BASE_URL + endpoint

    for attempt in range(2):  # 최대 2회 시도
        try:
            if http_method.upper() == "GET":
                response = requests.get(url, headers=headers, params=signed_params)
            else:
                response = requests.request(http_method.upper(), url, headers=headers, params=signed_params)
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            try:
                err = e.response.json()
                print("[Binance 응답]", err)
                if err.get("code") == -1022 and attempt == 0:
                    print("⏳ Signature 오류로 재시도 중...")
                    continue
            except:
                print("[Binance 예외]", e)
            raise


def public_request(endpoint: str, params: dict = None) -> dict:
    """퍼블릭 엔드포인트 (서명 없이 GET)"""
    url = BASE_URL + endpoint
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_klines(symbol: str, interval: str, limit: int = 150) -> list:
    """캔들 데이터 조회"""
    return public_request("/fapi/v1/klines", {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    })


def get_price(symbol: str) -> float:
    """현재가 조회"""
    data = public_request("/fapi/v1/ticker/price", {"symbol": symbol})
    return float(data.get("price", 0))


def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """시장가 주문 (체결 정보 포함)"""
    try:
        return send_signed_request("POST", "/fapi/v1/order", {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
            "newOrderRespType": "FULL"
        })
    except HTTPError as e:
        try:
            err = e.response.json()
        except:
            err = {"error": str(e)}
        print(f"[Order Error] {symbol} {side} {quantity} → {err}")
        return err


def place_market_exit(symbol: str, side: str, quantity: float) -> dict:
    """청산 주문 (시장가)"""
    return place_market_order(symbol, side, quantity)


def get_account_info() -> dict:
    """계정 정보 (잔고·포지션 포함)"""
    return send_signed_request("GET", "/fapi/v2/account", {})


def get_balance() -> float:
    """USDT 잔고 조회"""
    account = get_account_info()
    for asset in account.get("assets", []):
        if asset.get("asset") == "USDT":
            return float(asset.get("availableBalance", 0.0))
    return 0.0


def get_position(symbol: str) -> dict:
    """심볼별 포지션 정보 조회"""
    account = get_account_info()
    for pos in account.get("positions", []):
        if pos.get("symbol") == symbol:
            return pos
    return {}
