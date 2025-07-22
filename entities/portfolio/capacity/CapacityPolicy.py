from __future__ import annotations
from typing import Protocol, List, Set
from entities.tradeManager.TradeProposal import TradeProposal
from entities.tradeManager.TradeEvent    import TradeEvent


class CapacityPolicy(Protocol):
    """
    Decide whether a *pending* TradeProposal may be enqueued.

    Parameters
    ----------
    proposal   : the proposal being evaluated
    now_ts     : orchestrator's current bar timestamp
    pending_q  : entry TradeEvents already queued (min-heap)
    open_syms  : symbols that currently have non-zero position

    Return
    ------
    bool – True to admit, False to reject
    """
    def admit(
        self,
        proposal  : TradeProposal,
        now_ts    : int,
        pending_q : List[TradeEvent],
        open_syms : Set[str],
    ) -> bool: ...
# ------------------------------------------------------------------ #
class LegCapacity:
    """Classic limit on total *entry legs*."""
    def __init__(self, max_legs: int = 5):
        self.max_legs = max_legs

    def admit(self, proposal, now_ts, pending_q, open_syms):
        queued_legs = sum(1 for e in pending_q if e.is_entry)
        opens_now   = sum(
            1
            for e in proposal.build_events()
            if e.is_entry and e.ts == now_ts
        )
        return queued_legs + opens_now <= self.max_legs


class SymbolCapacity:
    """Limit on concurrent *symbols* with exposure."""
    def __init__(self, max_symbols: int = 5):
        self.max_symbols = max_symbols

    def admit(self, proposal, now_ts, pending_q, open_syms):
        queued_syms = {e.meta["symbol"] for e in pending_q if e.is_entry}
        new_syms    = {
            e.meta["symbol"]
            for e in proposal.build_events()
            if e.is_entry and e.ts == now_ts
        }
        future_syms = open_syms | queued_syms | new_syms
        return len(future_syms) <= self.max_symbols
