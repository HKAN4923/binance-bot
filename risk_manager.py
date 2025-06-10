# File: risk_manager.py
from config import Config

class RiskManager:
    def __init__(self, client):
        self.client = client

    def position_size(self, price):
        balance = self.client.get_account_balance()
        alloc = balance * Config.MAX_EXPOSURE
        return alloc / price

    def can_enter(self, current_positions_count):
        return current_positions_count < Config.MAX_POSITIONS