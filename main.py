# main.py (최종 정리본 - 불필요한 import 제거 및 구조 정리)
from strategy_orb import check_entry as orb_entry, check_exit as orb_exit
from strategy_nr7 import check_entry as nr7_entry, check_exit as nr7_exit
from strategy_pullback import check_entry as pullback_entry, check_exit as pullback_exit
from strategy_ema_cross import check_entry as ema_entry, check_exit as ema_exit
from trade_summary import print_open_positions
import time

# 고정 심볼 리스트 (시장 안정성 기준)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "BCHUSDT", "INJUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "IMXUSDT", "SUIUSDT", "RNDRUSDT",
    "TONUSDT", "FILUSDT", "PEPEUSDT", "TUSDT", "STXUSDT", "WIFUSDT", "TIAUSDT", "NEARUSDT", "DYDXUSDT", "COTIUSDT",
    "MASKUSDT", "1000FLOKIUSDT", "BLZUSDT", "CFXUSDT", "1000XECUSDT", "ACHUSDT", "ALICEUSDT", "GMTUSDT", "KLAYUSDT", "HBARUSDT",
    "TRXUSDT", "CKBUSDT", "GALUSDT", "WAVESUSDT", "TOMOUSDT", "MAGICUSDT", "DUSKUSDT", "ONEUSDT", "SKLUSDT", "SANDUSDT",
    "AGIXUSDT", "OCEANUSDT", "ZILUSDT", "RLCUSDT", "FLOWUSDT", "PHBUSDT", "LINAUSDT", "VETUSDT", "PERPUSDT", "GRTUSDT",
    "XEMUSDT", "CHRUSDT", "CTSIUSDT", "BETAUSDT", "ENSUSDT", "FXSUSDT", "HIGHUSDT", "JOEUSDT", "KAVAUSDT", "KNCUSDT",
    "LITUSDT", "LOOMUSDT", "MKRUSDT", "MINAUSDT", "NKNUSDT", "OXTUSDT", "QTUMUSDT", "RAYUSDT", "REEFUSDT", "ROSEUSDT",
    "RSRUSDT", "SFPUSDT", "SNXUSDT", "STMXUSDT", "STORJUSDT", "SUNUSDT", "SXPUSDT", "THETAUSDT", "TLMUSDT", "UMAUSDT",
    "UNFIUSDT", "VTHOUSDT", "XNOUSDT", "YFIUSDT", "ZRXUSDT", "ZRXUSDT", "NMRUSDT", "ALPHAUSDT", "ANTUSDT", "BADGERUSDT"
]

# 전략별 진입 실행
def run_all_entries():
    for sym in SYMBOLS:
        orb_entry(sym)
        nr7_entry(sym)
        pullback_entry(sym)
        ema_entry(sym)

# 전략별 청산 실행
def run_all_exits():
    for sym in SYMBOLS:
        orb_exit(sym)
        nr7_exit(sym)
        pullback_exit(sym)
        ema_exit(sym)

# 메인 루프
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
