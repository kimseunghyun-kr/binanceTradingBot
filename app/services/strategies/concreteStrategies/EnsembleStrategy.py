# strategies/ensemble.py
from app.services.strategies.BaseStrategy import BaseStrategy

class EnsembleStrategy(BaseStrategy):
    def __init__(self, strategies, weights=None, method='weighted'):
        self.strategies = strategies
        self.weights = weights or [1 / len(strategies)] * len(strategies)
        self.method = method
    def decide(self, df, interval, **kwargs):
        # Stub logic: just runs all and picks the first 'BUY'
        for s in self.strategies:
            d = s.decide(df, interval, **kwargs)
            if d['signal'] == 'BUY':
                return d
        return {
            'signal': 'NO',
            'entry_price': None,
            'tp_price': None,
            'sl_price': None,
            'confidence': 0,
            'meta': {},
            'strategy_name': 'EnsembleStrategy'
        }
