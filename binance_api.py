# binance_api.py
import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
BASE_URL = "https://fapi.binance.com"

headers = {
    "X-MBX-APIKEY": API_KEY
}

def get_timestamp():
    return int(time.time() * 1000)

def sign(params):
    query_string = urlencode(params)
    return hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def send_signed_request(http_method, url_path, payload={}):
    params = {
        **payload,
        "timestamp": get_timestamp()
    }
    params["signature"] = sign(params)
    url = BASE_URL + url_path
    if http_method == "GET":
        return requests.get(url, headers=headers, params=params).json()
    elif http_method == "POST":
        return requests.post(url, headers=headers, params=params).json()
    elif http_method == "DELETE":
        return requests.delete(url, headers=headers, params=params).json()

def get_price(symbol):
    url = f"{BASE_URL}/fapi/v1/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

def get_klines(symbol, interval="5m", limit=100):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    return requests.get(url).json()

def get_balance():
    result = send_signed_request("GET", "/fapi/v2/account")
    balance_info = next(b for b in result['assets'] if b['asset'] == 'USDT')
    return float(balance_info['availableBalance'])

def place_limit_order(symbol, side, quantity, price):
    return send_signed_request("POST", "/fapi/v1/order", {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": quantity,
        "price": str(price)
    })

def place_market_order(symbol, side, quantity):
    # newOrderRespType="FULL"을 써야 resp["fills"]가 반환됩니다.
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
def cancel_all_orders(symbol):
    return send_signed_request("DELETE", "/fapi/v1/allOpenOrders", {
        "symbol": symbol
    })

# binance_api.py 안에 추가
def place_market_exit(symbol, side, quantity):
    # 청산도 FULL 응답으로 체결 정보 받도록 직접 호출
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

