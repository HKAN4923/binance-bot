import threading
import time
from binance_client import BinanceClient
from config import Config  # ✅ 이 줄이 필요합니다

class SLTPCleaner:
    def __init__(self, client: BinanceClient):
        self.client = client
        self.interval = Config.CLEANUP_INTERVAL  # ✅ config ❌ → Config ✅
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        while True:
            self.client.cancel_all_sltp()
            time.sleep(self.interval)
