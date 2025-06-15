from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pullback_entry, check_exit as pullback_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from trade_summary import print_open_positions
from position_manager import get_open_position_count
import time

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "BCHUSDT", "INJUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "IMXUSDT", "SUIUSDT", "RNDRUSDT",
    "NEARUSDT", "TIAUSDT", "TONUSDT", "WIFUSDT", "JASMYUSDT", "ENSUSDT", "PEPEUSDT", "SHIBUSDT", "TRXUSDT", "ATOMUSDT",
    "FTMUSDT", "SANDUSDT", "AAVEUSDT", "DYDXUSDT", "FLOWUSDT", "GALAUSDT", "RUNEUSDT", "HBARUSDT", "STXUSDT", "COTIUSDT",
    "XLMUSDT", "CFXUSDT", "BLZUSDT", "MAGICUSDT", "MASKUSDT", "ZILUSDT", "ONEUSDT", "ALGOUSDT", "BANDUSDT", "GMTUSDT"
]

def run_all_entries():
    open_pos = get_open_position_count()
    max_pos = 4
    if open_pos >= max_pos:
        print(f"분석중...({open_pos}/{max_pos})")
        return
    for sym in SYMBOLS:
        if get_open_position_count() >= max_pos:
            break
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