# main.py

import os
import time
import math
import asyncio
import pytz
import schedule
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Bot
from ta.momentum import RSIIndicator, StochasticOscillator, StochRSIIndicator, WilliamsRIndicator
from ta.trend import EMAIndicator, MACD, ADXIndicator, CCIIndicator
from ta.volatility import AverageTrueRange

# ─── 환경 변수 로드 ──────────────────────────────────────────────────────────────
load_dotenv()
API_KEY          = os.getenv("BINANCE_API_KEY")
API_SECRET       = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KST              = pytz.timezone("Asia/Seoul")

# ─── 바이낸스 클라이언트 초기화 ─────────────────────────────────────────────────
exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {"defaultType": "future"}
})
bot = Bot(token=TELEGRAM_TOKEN)

# ─── 설정값 ─────────────────────────────────────────────────────────────────────
LEVERAGE                  = 10
RISK_RATIO                = 0.3
MAX_POSITIONS             = 3
ANALYSIS_INTERVAL         = 10        # 초
MONITOR_INTERVAL          = 1         # 초
TELEGRAM_SUMMARY_INTERVAL = 1800      # 초
EMA_SHORT                 = 9
EMA_LONG                  = 21
RSI_PERIOD                = 14
ATR_PERIOD                = 14
OSC_PERIOD                = 14
MIN_ADX                   = 20
RR_RATIO                  = 1.3
EARLY_EXIT_PCT            = 0.01      # 1%

# ─── 전역 변수 ─────────────────────────────────────────────────────────────────
positions      = {}   # {symbol: {...}}
trade_history  = []   # [{'symbol','side','entry_time','exit_time','pnl','pnl_pct'}]
last_summary   = datetime.now(pytz.utc) - timedelta(seconds=TELEGRAM_SUMMARY_INTERVAL)
last_morning   = None
last_evening   = None

# ─── 유틸: 텔레그램 전송 ─────────────────────────────────────────────────────────
def send_telegram(text: str):
    """비동기 send_message 래퍼"""
    asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text))

# ─── 유틸: 거래 가능 심볼 필터 ──────────────────────────────────────────────────
def get_trade_symbols():
    info = exchange.load_markets()
    return [s for s, m in info.items()
            if s.endswith("/USDT") and m["active"]]

# ─── OHLCV 조회 ─────────────────────────────────────────────────────────────────
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 100):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    df.set_index("t", inplace=True)
    return df

# ─── 지표 계산 ─────────────────────────────────────────────────────────────────
def calc_indicators(df: pd.DataFrame):
    df["rsi"]       = RSIIndicator(df["c"], RSI_PERIOD).rsi()
    df["macd_diff"] = MACD(df["c"]).macd_diff()
    df["ema_short"] = EMAIndicator(df["c"], EMA_SHORT).ema_indicator()
    df["ema_long"]  = EMAIndicator(df["c"], EMA_LONG).ema_indicator()
    df["adx"]       = ADXIndicator(df["h"], df["l"], df["c"], RSI_PERIOD).adx()
    df["stoch"]     = StochasticOscillator(df["h"], df["l"], df["c"], OSC_PERIOD).stoch()
    df["atr"]       = AverageTrueRange(df["h"], df["l"], df["c"], ATR_PERIOD).average_true_range()
    return df.dropna()

# ─── 진입 시그널 판단 ───────────────────────────────────────────────────────────
def check_entry(symbol: str):
    df1h = fetch_ohlcv(symbol, "1h")
    df1h = calc_indicators(df1h)
    if df1h["adx"].iloc[-1] < MIN_ADX:
        return None
    last = df1h.iloc[-1]
    ls = sum([last["rsi"]<40, last["macd_diff"]>0, last["c"]>last["ema_long"], last["stoch"]<20])
    ss = sum([last["rsi"]>60, last["macd_diff"]<0, last["c"]<last["ema_long"], last["stoch"]>80])
    cl = sum([last["macd_diff"]>0, last["c"]>last["ema_long"], last["adx"]>MIN_ADX])
    cs = sum([last["macd_diff"]<0, last["c"]<last["ema_long"], last["adx"]>MIN_ADX])
    if cl>=2 and ls>=3: return "long"
    if cs>=2 and ss>=3: return "short"
    return None

# ─── 동적 TP/SL 계산 ────────────────────────────────────────────────────────────
def dynamic_tp_sl(entry_price: float, adx: float, side: str):
    if adx >= 25:
        tp_mul, sl_mul = 3.0, 1.5
    elif adx >= 20:
        tp_mul, sl_mul = 2.5, 1.2
    else:
        tp_mul, sl_mul = 2.0, 1.0
    atr = entry_price * 0.005
    if side=="long":
        tp = entry_price + atr*tp_mul
        sl = entry_price - atr*sl_mul
    else:
        tp = entry_price - atr*tp_mul
        sl = entry_price + atr*sl_mul
    return round(tp,4), round(sl,4)

# ─── 진입 및 주문 함수 ─────────────────────────────────────────────────────────
def enter_position(symbol: str, side: str):
    balance = exchange.fetch_balance()["total"]["USDT"]
    price   = exchange.fetch_markets() # dummy to avoid error
    price   = float(exchange.fetch_ticker(symbol)["last"])
    amount  = round(balance * RISK_RATIO * LEVERAGE / price, 3)
    df1h    = calc_indicators(fetch_ohlcv(symbol, "1h"))
    adx     = df1h["adx"].iloc[-1]
    tp, sl  = dynamic_tp_sl(price, adx, side)
    exchange.create_market_order(symbol, "buy" if side=="long" else "sell", amount)
    # TP/SL 주문
    exchange.create_order(symbol, "TAKE_PROFIT_MARKET",
                          "sell" if side=="long" else "buy",
                          amount, None,
                          {"stopPrice":tp,"closePosition":True})
    exchange.create_order(symbol, "STOP_MARKET",
                          "sell" if side=="long" else "buy",
                          amount, None,
                          {"stopPrice":sl,"closePosition":True})
    now = datetime.now(pytz.utc)
    positions[symbol] = {
        "side":side,
        "entry_price":price,
        "amount":amount,
        "entry_time":now
    }
    send_telegram(f"🔹 ENTRY {symbol} | {side.upper()}\nEntry: {price:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}")

# ─── 청산 처리 함수 ────────────────────────────────────────────────────────────
def close_position(symbol: str, reason: str):
    pos = positions.pop(symbol, None)
    if not pos: return
    side = "sell" if pos["side"]=="long" else "buy"
    try:
        exchange.create_market_order(symbol, side, pos["amount"])
    except: pass
    exit_price = float(exchange.fetch_ticker(symbol)["last"])
    pnl      = (exit_price-pos["entry_price"])*pos["amount"] if pos["side"]=="long" else (pos["entry_price"]-exit_price)*pos["amount"]
    pnl_pct  = pnl/(pos["entry_price"]*pos["amount"])*100
    trade_history.append({
        "symbol":symbol,
        "side":pos["side"],
        "entry_time":pos["entry_time"],
        "exit_time":datetime.now(pytz.utc),
        "pnl":pnl,
        "pnl_pct":pnl_pct
    })
    send_telegram(f"🔸 EXIT {symbol} | {reason}\nPnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)")

# ─── 포지션 모니터링 ────────────────────────────────────────────────────────────
def manage_positions():
    now = datetime.now(pytz.utc)
    global last_summary, last_morning, last_evening
    # 포지션별 관리
    for sym, pos in list(positions.items()):
        age = now - pos["entry_time"]
        if age >= timedelta(hours=2):
            close_position(sym, "TIMEOUT")
        elif age >= timedelta(hours=1,minutes=30):
            new = check_entry(sym)
            if new and new!=pos["side"]:
                close_position(sym, "RE-EVALUATE")
    # 30분 요약
    if (now-last_summary).total_seconds()>=TELEGRAM_SUMMARY_INTERVAL:
        if positions:
            msg="📊 Position Update\n"
            for sym,pos in positions.items():
                cur = float(exchange.fetch_ticker(sym)["last"])
                pnl = (cur-pos["entry_price"])*pos["amount"] if pos["side"]=="long" else (pos["entry_price"]-cur)*pos["amount"]
                pct = pnl/(pos["entry_price"]*pos["amount"])*100
                msg+=f"{sym} | {pos['side']} | PnL: {pnl:.2f} ({pct:.2f}%)\n"
            send_telegram(msg)
        last_summary=now
    # 점호
    now_kst = datetime.now(KST)
    today = now_kst.date()
    # 아침
    if now_kst.hour==6 and now_kst.minute==30 and last_morning!=today:
        start = datetime.combine(today-timedelta(days=1), datetime.min.time(), tzinfo=KST).replace(hour=21,minute=30)
        end = datetime.combine(today, datetime.min.time(), tzinfo=KST).replace(hour=6,minute=30)
        report_period(start,end,"아침 점호")
        last_morning=today
    # 저녁
    if now_kst.hour==21 and now_kst.minute==30 and last_evening!=today:
        start = datetime.combine(today, datetime.min.time(), tzinfo=KST).replace(hour=6,minute=30)
        end = datetime.combine(today, datetime.min.time(), tzinfo=KST).replace(hour=21,minute=30)
        report_period(start,end,"저녁 점호")
        last_evening=today

# ─── 점호 리포트 생성 ────────────────────────────────────────────────────────────
def report_period(start,end,title):
    period = [t for t in trade_history if start<=t["exit_time"].astimezone(KST)<=end]
    total = len(period)
    wins = sum(1 for t in period if t["pnl"]>0)
    losses = total-wins
    profit = sum(t["pnl"] for t in period)
    winrate = (wins/total*100) if total else 0
    # 전체 승률 (오늘 자정 이후)
    midnight = datetime.combine(end.date(), datetime.min.time(), tzinfo=KST)
    today_trades=[t for t in trade_history if t["exit_time"].astimezone(KST)>=midnight]
    tw = sum(1 for t in today_trades if t["pnl"]>0)
    tl = len(today_trades)-tw
    trate = (tw/len(today_trades)*100) if today_trades else 0
    msg = f"📒 {title}\n기간: {start.strftime('%m/%d %H:%M')}~{end.strftime('%m/%d %H:%M')}\n"\
          f"거래: {total}회  손익: {profit:.2f} USDT\n"\
          f"{wins}승 {losses}패  승률: {winrate:.2f}%\n"\
          f"오늘 전체 승률: {trate:.2f}%"
    send_telegram(msg)

# ─── 메인 루프 ─────────────────────────────────────────────────────────────────
def main():
    send_telegram("🤖 Bot started.")
    symbols = get_trade_symbols()
    while True:
        try:
            # 진입 로직
            if len(positions)<MAX_POSITIONS:
                for sym in symbols:
                    if sym in positions: continue
                    sig = check_entry(sym)
                    if sig:
                        enter_position(sym,sig)
                        break
            # 관리
            manage_positions()
            time.sleep(ANALYSIS_INTERVAL)
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
