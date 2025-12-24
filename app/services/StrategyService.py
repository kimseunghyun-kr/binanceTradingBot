from typing import List, Dict

from strategyOrchestrator.entities.strategies.BaseStrategy import BaseStrategy
from strategyOrchestrator.entities.strategies.concreteStrategies.EnsembleStrategy import EnsembleStrategy
from strategyOrchestrator.entities.strategies.concreteStrategies.FundingFibRetracementStrategy import (
    FundingFibRetracementStrategy
)
from strategyOrchestrator.entities.strategies.concreteStrategies.MomentumStrategy import MomentumStrategy
from strategyOrchestrator.entities.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy


class StrategyService:
    """Service for strategy creation and metadata management."""
    # Built-in strategy definitions (could be extended or stored in DB)
    BUILT_IN_STRATEGIES: List[Dict[str, str]] = [
        {"name": "peak_ema_reversal",
         "description": "Single-peak detection with EMA pullback (PeakEMAReversalStrategy)"},
        {"name": "momentum", "description": "Simple momentum strategy based on price window (MomentumStrategy)"},
        {"name": "ensemble", "description": "Ensemble of multiple strategies (combined signal)"},
        {"name": "funding_fib_retracement",
         "description": "Funding negative + Fibonacci retracement with low-volume pullback"}
    ]

    @staticmethod
    def get_strategy_instance(name: str, params: Dict) -> BaseStrategy:
        """
        Factory method: Create a strategy instance by name with given parameters.
        Raises ValueError if strategy name is unknown.
        """
        name = name.lower()
        if name == "peak_ema_reversal":
            # Create PeakEMAReversalStrategy with any provided params (tp_ratio, sl_ratio, etc.)
            return PeakEMAReversalStrategy(**params)
        elif name == "momentum":
            return MomentumStrategy(**params)
        elif name == "ensemble":
            # Expect 'strategies' list in params for ensemble
            strategies_spec = params.get("strategies")
            if not strategies_spec:
                raise ValueError("Ensemble strategy requires a 'strategies' list")
            sub_strategies = []
            weights = []
            # Recursively create each sub-strategy in the ensemble
            for strat_cfg in strategies_spec:
                sub_name = strat_cfg.get("name")
                sub_params = strat_cfg.get("params", {})
                weight = strat_cfg.get("weight", 1.0)
                sub_strategies.append(StrategyService.get_strategy_instance(sub_name, sub_params))
                weights.append(weight)
            return EnsembleStrategy(sub_strategies, weights=weights)
        elif name == "funding_fib_retracement":
            return FundingFibRetracementStrategy(**params)
        else:
            # Unknown strategy
            raise ValueError(f"Unknown strategy name: {name}")
