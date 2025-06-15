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

# ✅ .env 파일 로드
from pathlib import Path
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
API_SECRET_RAW = os.getenv("BINANCE_API_SECRET", "").strip()
API_SECRET = API_SECRET_RAW.encode("utf-8")

if not API_KEY or not API_SECRET_RAW:
    raise ValueError("❌ .env에서 API 키 또는 시크릿이 누락되었습니다.")

# 단 1번만 인코딩
API_SECRET = API_SECRET_RAW.encode("utf-8")

print(f"[🔑] API_KEY: {API_KEY[:6]}...{API_KEY[-4:]}")
print(f"[🔐] API_SECRET: {API_SECRET_RAW[:6]}...{API_SECRET_RAW[-4:]}")

BASE_URL = "https://fapi.binance.com"

def get_server_time() -> int:
    url = BASE_URL + "/fapi/v1/time"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["serverTime"]

def _get_timestamp_ms():
    try:
        return get_server_time()
    except:
        return int(time.time() * 1000)

def _sign_payload(params: dict) -> dict:
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    print("[DEBUG] Signing:", query_string)
    signature = hmac.new(
        API_SECRET,
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    return params

def send_signed_request(http_method: str, endpoint: str, params: dict) -> dict:
    params.update({
        "timestamp": _get_timestamp_ms(),
        "recvWindow": 5000
    })
    signed_params = _sign_payload(params)
    headers = {"X-MBX-APIKEY": API_KEY}
    url = BASE_URL + endpoint

    for attempt in range(2):
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
    url = BASE_URL + endpoint
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_klines(symbol: str, interval: str, limit: int = 150) -> list:
    return public_request("/fapi/v1/klines", {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    })

def get_price(symbol: str) -> float:
    data = public_request("/fapi/v1/ticker/price", {"symbol": symbol})
    return float(data.get("price", 0))

def place_market_order(symbol: str, side: str, quantity: float) -> dict:
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
    return place_market_order(symbol, side, quantity)

def get_account_info() -> dict:
    return send_signed_request("GET", "/fapi/v2/account", {})

def get_balance() -> float:
    account = get_account_info()
    for asset in account.get("assets", []):
        if asset.get("asset") == "USDT":
            return float(asset.get("availableBalance", 0.0))
    return 0.0

def get_position(symbol: str) -> dict:
    account = get_account_info()
    for pos in account.get("positions", []):
        if pos.get("symbol") == symbol:
            return pos
    return {}
