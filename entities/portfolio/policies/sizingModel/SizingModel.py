from typing import Protocol
from entities.tradeManager.TradeMeta import TradeMeta

def fixed_fraction(frac: float):
    """Example: scale every entry by constant fraction (e.g. 0.5)."""
    return lambda *_, **__: frac
