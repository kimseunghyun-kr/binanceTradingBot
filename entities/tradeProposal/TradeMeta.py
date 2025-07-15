from dataclasses import dataclass

from dataclasses import dataclass

@dataclass(frozen=True)
class TradeMeta:
    symbol: str
    entry_time: int
    entry_price: float
    tp_price: float
    sl_price: float
    size: float = 1
    direction: str = "LONG"   # "LONG" or "SHORT"
