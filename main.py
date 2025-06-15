from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pullback_entry, check_exit as pullback_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from trade_summary import print_open_positions
from binance.client import Client
from dotenv import load_dotenv
import os, time

load_dotenv()
client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

def load_symbols(top_n=100):
    try:
        tickers = client.futures_ticker_24hr()
        exchange_info = client.futures_exchange_info()
        valid = {
            s["symbol"]
            for s in exchange_info["symbols"]
            if s["contractType"] == "PERPETUAL"
            and s["symbol"].endswith("USDT")
            and s["status"] == "TRADING"
        }
        filtered = [t for t in tickers if t["symbol"] in valid]
        sorted_symbols = sorted(filtered, key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [s["symbol"] for s in sorted_symbols[:top_n]]
    except Exception as e:
        print(f"[ERROR] 심볼 로딩 실패: {e}")
        return ["BTCUSDT", "ETHUSDT"]

SYMBOLS = load_symbols()

def run_all_entries():
    for sym in SYMBOLS:
        orb_entry(sym)
        nr7_entry(sym)
        pullback_entry(sym)
        ema_entry(sym)

def run_all_exits():
    for sym in SYMBOLS:
        orb_exit(sym)
        nr7_exit(sym)
        pullback_exit(sym)
        ema_exit(sym)

def main():
    last_status_time = 0
    while True:
        now = time.time()
        try:
            run_all_entries()
            run_all_exits()
        except Exception as e:
            print(f"[메인 루프 오류] {e}")

        if now - last_status_time >= 10:
            print_open_positions()
            last_status_time = now

        time.sleep(10)

if __name__ == "__main__":
    main()