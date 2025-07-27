"""
portfolio/policies/interfaces.py
──────────────────────────────────────────────────────────────────────────
Canonical Protocols for ALL pluggable portfolio based policies.

We favour structural typing: a plain function that matches the
signature is as good as a subclass.
"""

from __future__ import annotations

from typing import Protocol, List, Set

from strategyOrchestrator.entities.tradeManager.TradeEvent import TradeEvent
from strategyOrchestrator.entities.tradeManager.TradeMeta import TradeMeta


# ───────────────────────────────── cost models ───────────────────────── #

class EventCostModel(Protocol):
    """fee / slippage : pct = f(event)"""
    def __call__(self, event: TradeEvent) -> float: ...


# ───────────────────────────────── sizing model ──────────────────────── #

class SizingModel(Protocol):
    """
    Return a multiplicative scale for entry qty (1.0 = no change).

    meta  : TradeMeta for the proposal
    phase : "entry" | "dca" | "exit"   (only "entry" used here)
    """
    def __call__(self, meta: TradeMeta, phase: str) -> float: ...


# ───────────────────────────────── capacity policy ───────────────────── #

class CapacityPolicy(Protocol):
    def admit(
        self,
        proposal : "TradeProposal",
        now_ts   : int,
        pending_q: List[TradeEvent],
        open_syms: Set[str],
    ) -> bool: ...


