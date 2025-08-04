# strategyOrchestrator/registry.py
from functools import partial

# import concrete classes / callables
from strategyOrchestrator.entities.tradeManager.policies.FillPolicy import (
    AggressiveMarketPolicy, VWAPDepthPolicy
)
from strategyOrchestrator.entities.portfolio.policies.fees.fees import (
    FEE_STATIC, FEE_PER_SYMBOL, SLIP_RANDOM, SLIP_ZERO
)
from strategyOrchestrator.entities.portfolio.policies.capacity.CapacityPolicy import (
    LegCapacity, SymbolCapacity
)
from strategyOrchestrator.entities.portfolio.policies.sizingModel.SizingModel import (
    fixed_fraction
)
from strategyOrchestrator.entities.strategies.concreteStrategies.PeakEmaReversalStrategy import (
    PeakEMAReversalStrategy
)

################################################################################
# Maps **contain only callables** (classes, lambdas, partials) – never instances
################################################################################
FEE_MAP  = {"static": lambda: FEE_STATIC, "per_symbol": lambda: FEE_PER_SYMBOL}
SLIP_MAP = {"zero":   lambda: SLIP_ZERO,  "random":     lambda: SLIP_RANDOM}
FILL_MAP = {
    "AggressiveMarketPolicy": AggressiveMarketPolicy,  # class—needs fee/slip later
    "VWAPDepthPolicy":        VWAPDepthPolicy,
}
CAP_MAP  = {"LegCapacity": LegCapacity, "SymbolCapacity": SymbolCapacity}
SIZE_MAP = {"fixed_fraction": partial(fixed_fraction, 1.0),}
STRAT_MAP= {"PeakEMAReversalStrategy": PeakEMAReversalStrategy}
