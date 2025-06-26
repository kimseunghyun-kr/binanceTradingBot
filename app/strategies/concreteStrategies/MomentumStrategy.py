# strategies/momentum.py
from app.strategies.BaseStrategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    def __init__(self, window=20):
        self.window = window
    def decide(self, df, interval, **kwargs):
        # Stub logic: always NO
        return {
            'signal': 'NO',
            'entry_price': None,
            'tp_price': None,
            'sl_price': None,
            'confidence': 0,
            'meta': {},
            'strategy_name': 'MomentumStrategy'
        }
