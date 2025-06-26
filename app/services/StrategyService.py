from typing import List, Dict

from app.strategies.concreteStrategies.EnsembleStrategy import EnsembleStrategy
from app.strategies.concreteStrategies.MomentumStrategy import MomentumStrategy
from app.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy


class StrategyService:
    """Service for strategy creation and metadata management."""
    # Built-in strategy definitions (could be extended or stored in DB)
    BUILT_IN_STRATEGIES: List[Dict[str, str]] = [
        {"name": "peak_ema_reversal",
         "description": "Single-peak detection with EMA pullback (PeakEMAReversalStrategy)"},
        {"name": "momentum", "description": "Simple momentum strategy based on price window (MomentumStrategy)"},
        {"name": "ensemble", "description": "Ensemble of multiple strategies (combined signal)"}
    ]

    @staticmethod
    def get_strategy_instance(name: str, params: Dict) -> object:
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
        else:
            # Unknown strategy
            raise ValueError(f"Unknown strategy name: {name}")
