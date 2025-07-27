# entities/tradeManager/TradeEvent.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from strategyOrchestrator.entities.tradeManager.TradeEventType import TradeEventType


@dataclass(frozen=True, slots=True)
class TradeEvent:
    ts: int  # milliseconds epoch
    price: float
    qty: float  # +ve for long, –ve for short. can be fractional
    event: TradeEventType
    meta: Dict[str, Any] = field(default_factory=dict)

    # convenience helpers
    @property
    def is_entry(self) -> bool: return self.event == TradeEventType.OPEN

    @property
    def is_exit(self) -> bool: return self.event in {TradeEventType.REDUCE, TradeEventType.CLOSE}
