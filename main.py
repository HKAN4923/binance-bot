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

def load_symbols(top_n=50):
    try:
        tickers = client.get_ticker_24hr()
        usdt_pairs = [t for t in tickers if t["symbol"].endswith("USDT") and not t["symbol"].endswith("BUSD")]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
        symbols = [t["symbol"] for t in sorted_pairs[:top_n]]
        print(f"[INFO] 상위 {top_n}개 거래량 심볼 불러옴")
        return symbols
    except Exception as e:
        print(f"[ERROR] 심볼 로딩 실패: {e}")
        return ["BTCUSDT", "ETHUSDT"]

SYMBOLS = load_symbols(50)

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

        time.sleep(1)

if __name__ == "__main__":
    main()