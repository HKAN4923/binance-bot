from binance_api import client

def get_open_position_count():
    try:
        positions = client.futures_position_information()
        count = sum(
            1 for p in positions if float(p["positionAmt"]) != 0 and p["symbol"].endswith("USDT")
        )
        return count
    except Exception as e:
        print(f"[ERROR] get_open_position_count: {e}")
        return 0

def can_enter(symbol):
    try:
        positions = client.futures_position_information()
        for p in positions:
            if p["symbol"] == symbol and float(p["positionAmt"]) != 0:
                return False
        return True
    except Exception as e:
        print(f"[ERROR] can_enter({symbol}): {e}")
        return False
