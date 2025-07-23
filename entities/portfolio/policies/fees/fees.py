import random
from types import SimpleNamespace

from entities.portfolio.policies.interfaces import EventCostModel


def static_fee_model(meta, action="entry"):
    """Always returns the same fee percentage."""
    return 0.001  # 0.1%


def per_symbol_fee_model(meta, action="entry"):
    """Fee varies by symbol (could come from config/db)."""
    symbol_fees = {"BTCUSDT": 0.0005, "ETHUSDT": 0.001, "XRPUSDT": 0.0015}
    return symbol_fees.get(meta.symbol, 0.001)


def random_slippage_model(meta, action="entry"):
    """Random slippage for realism."""
    return random.uniform(0, 0.001)  # 0–0.1% per trade

# adapt to EventCostModel via a tiny wrapper
def _wrap_meta(fn):
    return lambda ev: fn(SimpleNamespace(symbol=ev.meta["symbol"]),"entry")

FEE_STATIC     : EventCostModel = _wrap_meta(static_fee_model)
FEE_PER_SYMBOL : EventCostModel = _wrap_meta(per_symbol_fee_model)
SLIP_RANDOM    : EventCostModel = _wrap_meta(random_slippage_model)
SLIP_ZERO      : EventCostModel = lambda ev: 0.0
