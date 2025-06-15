def log_trade(data):
    try:
        assert "tp" in data and "sl" in data, "[오류] TP/SL 누락됨"
        with open("trades.log", "a") as f:
            f.write(str(data) + "\n")
    except AssertionError as ae:
        print(f"[로그 저장 오류] {ae}")
    except Exception as e:
        print(f"[로그 저장 오류] {e}")