# entities/portfolio/TransactionManager.py
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

from .Position import Position
from .TradeEvent import TradeEvent

class TransactionManager:
    """
    Converts a time-ordered stream of TradeEvents into cash-flows
    and position state snapshots.  100 % deterministic & unit-testable.
    """
    def __init__(self, fee_model, slippage_model):
        self.positions: Dict[str, Position] = defaultdict(Position)
        self.cash_changes: List[tuple[int,float]] = []
        self.fee_model      = fee_model
        self.slippage_model = slippage_model

    def ingest(self, events: List[TradeEvent]):
        events.sort(key=lambda e: e.ts)
        for ev in events:
            slip = self.slippage_model(ev)
            fee  = self.fee_model(ev)
            px   = ev.price * (1 + slip + fee * (1 if ev.qty>0 else -1))
            notional = px * ev.qty * -1   # cash out for buy, in for sell
            self.cash_changes.append((ev.ts, notional))
            self.positions[ev.meta.get("symbol", "UNK")].apply(ev)

    # expose hooks for PortfolioManager
    def current_cash_delta(self) -> float:
        return sum(c for _,c in self.cash_changes)

    def unrealised_pnl(self, mark_prices: Dict[str,float]) -> float:
        pnl = 0.0
        for sym,pos in self.positions.items():
            pnl += pos.qty * (mark_prices.get(sym,pos.avg_px) - pos.avg_px)
        return pnl
