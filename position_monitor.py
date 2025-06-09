import threading
import time
import logging
from decimal import Decimal
from collections import deque
from binance_client import (
    get_balance,
    cancel_all_orders_for_symbol,
    get_position_info,
    get_mark_price,
    get_all_open_orders
)
from strategy import check_entry_signal
from telegram_notifier import send_telegram_message
from config import SYMBOLS, HEARTBEAT_INTERVAL

def monitor_positions():
    """
    Monitor open positions and send alerts
    """
    while True:
        try:
            for symbol in SYMBOLS:
                position = get_position_info(symbol)
                if position:
                    # Get current price
                    current_price = get_mark_price(symbol)
                    
                    # Calculate PnL
                    position_size = float(position['positionAmt'])
                    entry_price = float(position['entryPrice'])
                    
                    if position_size > 0:  # Long position
                        pnl = (current_price - entry_price) * position_size
                    else:  # Short position
                        pnl = (entry_price - current_price) * abs(position_size)
                    
                    # Send position update
                    message = f"Position Update:\n" \
                             f"Symbol: {symbol}\n" \
                             f"Position Size: {position_size}\n" \
                             f"Entry Price: {entry_price:.2f}\n" \
                             f"Current Price: {current_price:.2f}\n" \
                             f"PnL: {pnl:.2f} USDT"
                    send_telegram_message(message)
            
            time.sleep(HEARTBEAT_INTERVAL)
            
        except Exception as e:
            message = f"Error in position monitor: {str(e)}"
            send_telegram_message(message)
            time.sleep(60)

def heartbeat():
    """
    Periodic health check and logging
    """
    while True:
        try:
            # Get account info
            account = get_account_info()
            if account:
                # Log account status
                logging.info(f"Account health check: {account['accountType']}")
                
                # Check for any open orders
                for symbol in SYMBOLS:
                    orders = get_all_open_orders(symbol)
                    if orders:
                        logging.info(f"Open orders for {symbol}: {len(orders)}")
            
            time.sleep(HEARTBEAT_INTERVAL)
            
        except Exception as e:
            message = f"Error in heartbeat: {str(e)}"
            send_telegram_message(message)
            time.sleep(60)
