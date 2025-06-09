# strategy.py
import pandas as pd
import numpy as np
from binance.client import Client
from config import *
from binance_client import *
import logging
import time
from telegram_notifier import send_telegram_message

# 로깅 설정
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def calculate_atr(df, period=ATR_PERIOD):
    """
    Calculate Average True Range (ATR) for Linda Raschke's method
    """
    df['h-l'] = abs(df['high'] - df['low'])
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
    return df['atr']

def get_market_trend(df):
    """
    Determine market trend using ATR-based method
    """
    df['atr'] = calculate_atr(df)
    df['atr_threshold'] = df['atr'] * ATR_MULTIPLIER
    
    # 상승 추세 조건: 고가가 이전 고가보다 높고, ATR 기준선 위에 있는 경우
    df['uptrend'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['atr_threshold'])
    
    # 하락 추세 조건: 저가가 이전 저가보다 낮고, ATR 기준선 아래에 있는 경우
    df['downtrend'] = (df['low'] < df['low'].shift(1)) & (df['low'] < -df['atr_threshold'])
    
    return df[['uptrend', 'downtrend']]

def check_entry_signal(df):
    """
    Check for entry signals based on Linda Raschke's ATR breakout
    """
    df['atr'] = calculate_atr(df)
    df['entry_threshold'] = df['atr'] * ENTRY_THRESHOLD
    
    # Long entry signal: 가격이 이전 고가 + ATR 기준선 위로 돌파
    df['long_signal'] = (df['high'] > df['high'].shift(1) + df['entry_threshold'])
    
    # Short entry signal: 가격이 이전 저가 - ATR 기준선 아래로 돌파
    df['short_signal'] = (df['low'] < df['low'].shift(1) - df['entry_threshold'])
    
    return df[['long_signal', 'short_signal']]

def check_exit_signal(df):
    """
    Check for exit signals based on Linda Raschke's ATR retracement
    """
    df['atr'] = calculate_atr(df)
    df['exit_threshold'] = df['atr'] * EXIT_THRESHOLD
    
    # Exit signal: 가격이 이전 고가/저가에서 ATR 기준선 이내로 회귀
    df['exit_signal'] = ((df['high'] < df['high'].shift(1) + df['exit_threshold']) &
                        (df['low'] > df['low'].shift(1) - df['exit_threshold']))
    
    return df['exit_signal']

def execute_trade(symbol, side, quantity):
    """
    Execute trade with proper risk management and Telegram alerts
    """
    try:
        # Place market order
        order = place_order(symbol, side, quantity)
        logging.info(f"Order placed: {order}")
        
        # Get current position
        position = get_open_position(symbol)
        if position:
            entry_price = float(position['entryPrice'])
            
            # Calculate stop loss and take profit levels
            if side == 'BUY':
                sl_price = entry_price * (1 - STOP_LOSS_PERCENT/100)
                tp_price = entry_price * (1 + TAKE_PROFIT_PERCENT/100)
            else:
                sl_price = entry_price * (1 + STOP_LOSS_PERCENT/100)
                tp_price = entry_price * (1 - TAKE_PROFIT_PERCENT/100)
            
            # Set stop loss and take profit
            set_sl_tp(symbol, side, sl_price, tp_price, quantity)
            logging.info(f"Stop loss and take profit set for position: {position}")
            
            # Send Telegram alert
            message = f"New position opened:\n" \
                     f"Symbol: {symbol}\n" \
                     f"Side: {side}\n" \
                     f"Quantity: {quantity}\n" \
                     f"Entry Price: {entry_price:.2f}\n" \
                     f"Stop Loss: {sl_price:.2f}\n" \
                     f"Take Profit: {tp_price:.2f}"
            send_telegram_message(message)
            
            return True
    except Exception as e:
        logging.error(f"Trade execution error: {e}")
        return False

def check_position_status():
    """
    Check position status and send hourly updates
    """
    try:
        position = get_open_position(SYMBOL)
        if position:
            mark_price = get_mark_price(SYMBOL)
            position_size = float(position['positionAmt'])
            entry_price = float(position['entryPrice'])
            
            # Calculate PnL
            if position_size > 0:
                pnl = (mark_price - entry_price) * position_size
            else:
                pnl = (entry_price - mark_price) * abs(position_size)
            
            # Send status update
            message = f"Position Status:\n" \
                     f"Symbol: {SYMBOL}\n" \
                     f"Position Size: {position_size}\n" \
                     f"Entry Price: {entry_price:.2f}\n" \
                     f"Current Price: {mark_price:.2f}\n" \
                     f"PnL: {pnl:.2f} USDT"
            send_telegram_message(message)
            
    except Exception as e:
        logging.error(f"Error checking position status: {e}")

def main():
    """
    Main trading loop
    """
    while True:
        try:
            # Get latest market data
            df = get_klines(SYMBOL, TIMEFRAME)
            
            # Calculate indicators
            trend = get_market_trend(df)
            entry_signals = check_entry_signal(df)
            exit_signals = check_exit_signal(df)
            
            # Check current position
            position = get_open_position(SYMBOL)
            
            if position:
                # Check exit conditions
                if exit_signals.iloc[-1]:
                    # Close position
                    side = 'SELL' if float(position['positionAmt']) > 0 else 'BUY'
                    execute_trade(SYMBOL, side, abs(float(position['positionAmt'])))
                    logging.info(f"Position closed: {position}")
                    
                    # Send Telegram alert for position close
                    message = f"Position closed:\n" \
                             f"Symbol: {SYMBOL}\n" \
                             f"Side: {side}\n" \
                             f"Quantity: {abs(float(position['positionAmt']))}"
                    send_telegram_message(message)
            else:
                # Check entry conditions
                if entry_signals['long_signal'].iloc[-1]:
                    execute_trade(SYMBOL, 'BUY', QUANTITY)
                    logging.info("Long position opened")
                elif entry_signals['short_signal'].iloc[-1]:
                    execute_trade(SYMBOL, 'SELL', QUANTITY)
                    logging.info("Short position opened")
            
            # Check position status every hour
            check_position_status()
            
            # Wait for next interval
            time.sleep(HEARTBEAT_INTERVAL)
            
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
