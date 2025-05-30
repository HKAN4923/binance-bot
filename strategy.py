import ta

def check_entry(df):
    try:
        df = df.copy()
        df.dropna(inplace=True)
        df['rsi']   = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        macd        = ta.trend.MACD(df['close'])
        df['macd']          = macd.macd()
        df['macd_signal']   = macd.macd_signal()
        df['ema']           = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
        stoch       = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch']         = stoch.stoch()
        df['adx']           = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

        df.dropna(inplace=True)
        if df.empty or df.iloc[-1]['adx'] < 20:
            return None

        last = df.iloc[-1]
        ls = sum([last["rsi"]<40, last["macd"]>last["macd_signal"], last["close"]>last["ema"], last["stoch"]<20])
        ss = sum([last["rsi"]>60, last["macd"]<last["macd_signal"], last["close"]<last["ema"], last["stoch"]>80])
        cl = sum([last["macd"]>last["macd_signal"], last["close"]>last["ema"], last["adx"]>20])
        cs = sum([last["macd"]<last["macd_signal"], last["close"]<last["ema"], last["adx"]>20])

        if cl >= 2 and ls >= 3:
            return "long"
        if cs >= 2 and ss >= 3:
            return "short"
        return None
    except Exception:
        return None
