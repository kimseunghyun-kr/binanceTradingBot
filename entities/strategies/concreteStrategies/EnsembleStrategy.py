# strategies/ensemble.py
from entities.strategies.BaseStrategy import BaseStrategy


class EnsembleStrategy(BaseStrategy):
    """
    Ensemble strategy that aggregates multiple strategy signals.
    If any sub-strategy returns a BUY signal, the ensemble will signal BUY.
    Weights can be used for more complex decision logic (e.g., majority vote).
    """

    def __init__(self, strategies: list, weights=None, method: str = 'weighted'):
        self.strategies = strategies
        self.weights = weights or [1.0] * len(strategies)
        # Normalize weights
        total = sum(self.weights)
        if total != 0:
            self.weights = [w / total for w in self.weights]
        self.method = method

    def decide(self, df, interval, **kwargs):
        # Run each sub-strategy; return first BUY found (simple implementation)
        for strat in self.strategies:
            decision = strat.decide(df, interval, **kwargs)
            if decision.get('signal') == 'BUY':
                return decision  # return the first BUY signal's details
        # If none signaled BUY, return NO
        return {
            'signal': 'NO',
            'entry_price': None,
            'tp_price': None,
            'sl_price': None,
            'confidence': 0,
            'meta': {},
            'strategy_name': 'EnsembleStrategy'
        }
