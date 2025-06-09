# main.py
import os
from dotenv import load_dotenv
from binance_client import client, set_leverage
from config import *
import logging
import time
from strategy import main as strategy_main
from telegram_notifier import send_telegram_message
from utils import calculate_atr, calculate_quantity
from trade_summary import trade_summary
from position_monitor import monitor_positions, heartbeat

# 로깅 설정
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def initialize():
    """
    Initialize the trading bot
    """
    try:
        # Load environment variables
        load_dotenv()
        
        # Set leverage for all symbols
        set_leverage(SYMBOLS)
        
        # Send startup notification
        message = f"Trading bot started\n" \
                 f"Symbol: {SYMBOL}\n" \
                 f"Leverage: {LEVERAGE}x\n" \
                 f"Timeframe: {TIMEFRAME}"
        send_telegram_message(message)
        
        # Log initialization
        logging.info("Trading bot initialized successfully")
        
    except Exception as e:
        logging.error(f"Initialization error: {e}")
        raise

def main():
    """
    Main function to run the trading bot
    """
    try:
        initialize()
        
        # 모니터 스레드
        threading.Thread(target=monitor_positions, daemon=True).start()
        threading.Thread(target=heartbeat, daemon=True).start()

        # 메인 트레이딩 루프
        while True:
            for sym in SYMBOLS:
                df = get_klines(sym, '1m', limit=100)
                sig = check_entry(df)
                if sig:
                    qty = calculate_quantity(sym)
                    order = place_order(sym, sig, qty)
                    entry_price = float(order['avgFillPrice'])
                    atr = calculate_atr(df).iloc[-1]
                    if sig == 'BUY':
                        sl = entry_price - atr
                        tp = entry_price + atr
                        side = 'SELL'
                    else:
                        sl = entry_price + atr
                        tp = entry_price - atr
                        side = 'BUY'
                    set_sl_tp(sym, side, sl_price=round(sl, 2), tp_price=round(tp, 2), quantity=qty)
                    send_telegram_message(
                        f"✏️ Entry {sig} {sym}\nqty={qty}\nentry={entry_price:.2f} SL={sl:.2f} TP={tp:.2f}"
                    )
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Trading bot stopped by user")
        message = "Trading bot stopped by user"
        send_telegram_message(message)
    except Exception as e:
        logging.error(f"Main loop error: {e}")
        message = f"Error in trading bot: {str(e)}"
        send_telegram_message(message)
        time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
