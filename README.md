# Linda Raschke Trading Bot

This trading bot implements Linda Raschke's trading method using Binance Futures. It uses ATR-based entry and exit signals with proper risk management.

## Features

- ATR-based entry and exit signals
- 5x leverage trading
- Telegram alerts for position entries and exits
- Hourly position status updates
- Automatic stop loss and take profit orders
- Logging of all trading activities

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your credentials:
```
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
TELEGRAM_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

3. Run the bot:
```bash
python main.py
```

## Configuration

The bot can be configured through `config.py`:

- `SYMBOL`: Trading pair (default: BTCUSDT)
- `LEVERAGE`: Trading leverage (default: 5x)
- `QUANTITY`: Trading quantity in BTC
- `STOP_LOSS_PERCENT`: Stop loss percentage (default: 2%)
- `TAKE_PROFIT_PERCENT`: Take profit percentage (default: 1%)

## Risk Management

- Maximum position size is set to 0.1 BTC
- Stop loss is set at 2% of entry price
- Take profit is set at 1% of entry price
- ATR-based entry and exit thresholds are used for proper risk management

## Monitoring

The bot sends hourly status updates to your Telegram chat with:
- Current position size
- Entry price
- Current price
- PnL in USDT

## Error Handling

The bot includes robust error handling with:
- Automatic retry on errors
- Detailed logging
- Telegram alerts for critical errors
- Graceful shutdown on keyboard interrupt
