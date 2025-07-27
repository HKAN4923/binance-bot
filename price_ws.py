import json
import threading
import websocket
import logging

price_cache = {}  # 실시간 가격 저장 딕셔너리

def _on_message(ws, message):
    try:
        outer = json.loads(message)
        data = outer.get("data", {})  # ✅ 진짜 데이터는 여기 있음
        symbol = data.get("s")
        price_str = data.get("c")
        if symbol and price_str:
            price_cache[symbol.upper()] = float(price_str)
        else:
            logging.warning(f"[WebSocket 경고] 유효하지 않은 데이터 수신: {outer}")
    except Exception as e:
        logging.error(f"[WebSocket 오류] 메시지 처리 실패: {e}")

def _on_error(ws, error):
    logging.error(f"[WebSocket 오류] {error}")

def _on_close(ws, close_status_code, close_msg):
    logging.warning("[WebSocket 종료] 연결이 닫혔습니다")

def _run_ws(symbols):
    stream_names = [f"{s.lower()}@ticker" for s in symbols]
    url = f"wss://fstream.binance.com/stream?streams={'/'.join(stream_names)}"
    ws = websocket.WebSocketApp(
        url,
        on_message=_on_message,
        on_error=_on_error,
        on_close=_on_close,
    )
    ws.run_forever()

def start_price_ws(symbols):
    thread = threading.Thread(target=_run_ws, args=(symbols,), daemon=True)
    thread.start()
    logging.info("[WebSocket] 실시간 가격 수신 시작됨")

def get_price(symbol):
    return price_cache.get(symbol.upper(), 0.0)

def is_price_ready(symbol):
    """WebSocket 가격이 준비되었는지 확인"""
    return symbol.upper() in price_cache and price_cache[symbol.upper()] > 0
