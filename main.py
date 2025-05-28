# main.py

import time
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import pytz

# ====== 설정 ======
API_BASE = 'https://fapi.binance.com'
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
CHAT_ID        = 'YOUR_CHAT_ID'
# ==================

# 보관할 상태
open_positions = {}
trade_history = []  # {'symbol','profit','time','exit_time'}

# 텔레그램 전송
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode":"Markdown"})

# Kline 조회
def get_klines(symbol, interval, limit=100):
    url = f"{API_BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        't','o','h','l','c','v','ct','qav','nt','tbb','tbq','i'
    ])
    df['c'] = df['c'].astype(float)
    return df

# 지표 계산 (마지막 값만 리턴)
def calc_ind(df, length=14):
    return {
        'rsi': df['c'].ta.rsi(length=length).iloc[-1],
        'adx': df['c'].ta.adx(length=length)['ADX_'+str(length)].iloc[-1]
    }

# 진입 시그널 + 다중프레임 필터
def get_signal(symbol):
    df15 = get_klines(symbol, '15m', limit=100)
    df1h = get_klines(symbol, '1h', 100)

    ind15 = calc_ind(df15)
    ind1h = calc_ind(df1h)

    # 15m RSI 기반 단순 롱/숏
    sig = None
    if ind15['rsi'] < 30:
        sig = 'long'
    elif ind15['rsi'] > 70:
        sig = 'short'
    else:
        return None

    # 1시간봉 EMA 필터
    closes1h = df1h['c']
    ema20 = ta.ema(closes1h, length=20).iloc[-1]
    ema50 = ta.ema(closes1h, length=50).iloc[-1]
    ema200 = ta.ema(closes1h, length=200).iloc[-1]

    # 완전 반대 정렬일 때만 진입 금지
    if sig == 'long' and ema20 < ema50 < ema200:
        return None
    if sig == 'short' and ema20 > ema50 > ema200:
        return None

    return {'side': sig, 'adx': ind15['adx']}

# 동적 TP/SL 계산
def calc_tp_sl(price, adx, side):
    if adx >= 25:
        tp_mul, sl_mul = 3.0, 1.5
    elif adx >= 20:
        tp_mul, sl_mul = 2.5, 1.2
    else:
        tp_mul, sl_mul = 2.0, 1.0
    atr = price * 0.005  # ATR 대체(0.5%)
    if side=='long':
        tp = price + atr*tp_mul
        sl = price - atr*sl_mul
    else:
        tp = price - atr*tp_mul
        sl = price + atr*sl_mul
    return round(tp,2), round(sl,2)

# 진입 함수
def enter(symbol, info):
    side = info['side']; adx = info['adx']
    # 현재가
    df1 = get_klines(symbol,'1m',2)
    price = df1['c'].iloc[-1]
    tp, sl = calc_tp_sl(price, adx, side)

    open_positions[symbol] = {
        'entry_time': datetime.utcnow(),
        'price': price,
        'tp': tp,
        'sl': sl,
        'side': side,
        'rechecked': False
    }
    send_telegram(f"🚀 *ENTRY* {symbol} | {side.upper()}\nEntry: {price}\nTP: {tp} | SL: {sl}")

# 포지션 모니터링
def monitor():
    now = datetime.utcnow()
    for sym, pos in list(open_positions.items()):
        age = (now - pos['entry_time']).total_seconds()
        # 15분봉 종가
        price = get_klines(sym,'1m',2)['c'].iloc[-1]
        # PnL%
        pnl = ((price-pos['price'])/pos['price']*100) if pos['side']=='long' else ((pos['price']-price)/pos['price']*100)
        # 재검토 1h30m
        if age>=5400 and not pos['rechecked']:
            pos['rechecked']=True
            filt = get_signal(sym)
            if not filt or filt['side']!=pos['side']:
                _exit(sym, price, pnl, "RE-EVAL EXIT")
                continue
        # 2h 타임아웃
        if age>=7200:
            _exit(sym, price, pnl, "TIMEOUT EXIT")
            continue
        # TP/SL
        if (pos['side']=='long' and (price>=pos['tp'] or price<=pos['sl'])) or \
           (pos['side']=='short' and (price<=pos['tp'] or price>=pos['sl'])):
            _exit(sym, price, pnl, "TP/SL EXIT")

# 청산 공통
def _exit(sym, price, pnl, reason):
    open_positions.pop(sym,None)
    trade_history.append({'symbol':sym,'profit':pnl,'time':time.time()})
    send_telegram(f"💥 *{reason}* {sym}\nPrice: {price:.2f}\nPnL: {pnl:.2f}%")

# 아침/저녁 점호
def report():
    seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul)
    hhmm = now.strftime('%H:%M')
    # 새벽 이후 전체 승률 기준점
    base = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    # 아침 점호 (06:30)
    if hhmm=='06:30':
        # 전날 21:30 ~ 06:30
        end_ts   = now.timestamp()
        start_ts = (now - timedelta(hours=9)).replace(hour=21,minute=30,second=0).timestamp()
        _send_report(start_ts, end_ts, base, "[아침점호]")
        time.sleep(60)
    # 저녁 점호 (21:30)
    if hhmm=='21:30':
        # 당일 06:30 ~ 21:30
        start_ts = now.replace(hour=6,minute=30,second=0,microsecond=0).timestamp()
        end_ts   = now.timestamp()
        _send_report(start_ts, end_ts, base, "[저녁점호]")
        time.sleep(60)

def _send_report(s, e, base, label):
    period = [t for t in trade_history if s<=t['time']<=e]
    total = len(period)
    wins  = sum(1 for t in period if t['profit']>0)
    losses= total - wins
    pnl   = sum(t['profit'] for t in period)
    wr    = round(wins/total*100,2) if total else 0.0
    overall = [t for t in trade_history if t['time']>=base]
    ototal = len(overall)
    owins   = sum(1 for t in overall if t['profit']>0)
    owr     = round(owins/ototal*100,2) if ototal else 0.0

    msg = f"{label} {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%m/%d %H:%M')}\n"
    msg+= f"거래: {total}회  손익합: {pnl:.2f}%\n"
    msg+= f"{wins}승 {losses}패  승률: {wr}%\n"
    msg+= f"전체(오늘) 승률: {owr}%"
    send_telegram(msg)

# 메인 루프
def main():
    symbols = ['BTCUSDT','ETHUSDT']  # 원하면 추가
    while True:
        report()
        for sym in symbols:
            if sym not in open_positions:
                sig = get_signal(sym)
                if sig:
                    enter(sym, sig)
        monitor()
        time.sleep(15)

if __name__=="__main__":
    main()
