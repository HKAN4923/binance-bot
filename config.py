# 파일명: config.py
# 봇 운영 환경 및 스케줄 설정 모듈

import os
from dotenv import load_dotenv

load_dotenv()

# 최대 동시 보유 포지션 수
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
# 시장 분석 주기 (초 단위)
ANALYSIS_INTERVAL_SEC = int(os.getenv("ANALYSIS_INTERVAL_SEC", "10"))

# 텔레그램으로 거래 요약을 보낼 시각 리스트 (KST 기준 시, 분)
SUMMARY_TIMES = [
    (6, 30),
    (12, 0),
    (18, 0),
    (21, 30),
]

# 환경 변수 검증: 필수 설정 누락 시 오류
required = ["BINANCE_API_KEY", "BINANCE_API_SECRET", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
missing = [var for var in required if not os.getenv(var)]
if missing:
    raise RuntimeError(f"{', '.join(missing)} 환경 변수가 설정되지 않았습니다.")
