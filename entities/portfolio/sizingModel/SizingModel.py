from typing import Protocol
from entities.tradeManager.TradeMeta import TradeMeta


class SizingModel(Protocol):
    """
    Return a multiplicative scale for entry qty (1.0 = no change).

    meta  : TradeMeta for the proposal
    phase : "entry" | "dca" | "exit"   (only "entry" used here)
    """
    def __call__(self, meta: TradeMeta, phase: str) -> float: ...


def fixed_fraction(frac: float):
    """Example: scale every entry by constant fraction (e.g. 0.5)."""
    return lambda *_, **__: frac
