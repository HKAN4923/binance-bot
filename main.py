from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pullback_entry, check_exit as pullback_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from trade_summary import print_open_positions
from telegram_bot import send_telegram
import time

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "BCHUSDT", "INJUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "IMXUSDT", "SUIUSDT", "RNDRUSDT",
    "ATOMUSDT", "FILUSDT", "TONUSDT", "STXUSDT", "NEARUSDT", "FTMUSDT", "PEPEUSDT", "1000SHIBUSDT", "GALAUSDT", "HBARUSDT",
    "THETAUSDT", "CRVUSDT", "GMTUSDT", "COTIUSDT", "TWTUSDT", "FLOWUSDT", "AAVEUSDT", "ZILUSDT", "DYDXUSDT", "MASKUSDT",
    "AGIXUSDT", "XLMUSDT", "TRXUSDT", "YFIUSDT", "KAVAUSDT", "BLZUSDT", "WAVESUSDT", "ENJUSDT", "COMPUSDT", "JASMYUSDT"
]

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
    send_telegram("✅ 자동매매 봇이 시작되었습니다.")
    while True:
        now = time.time()
        try:
            run_all_entries()
            run_all_exits()
        except Exception as e:
            print(f"[메인 루프 오류] {e}")
            send_telegram(f"❗️메인 루프 오류 발생: {e}")
        if now - last_status_time >= 10:
            print_open_positions()
            last_status_time = now
        time.sleep(10)

if __name__ == "__main__":
    main()
