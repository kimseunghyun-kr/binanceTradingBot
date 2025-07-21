"""
Extension of your TransactionLedger that understands funding-only events
and works entirely in USD notionals (no external price feeds).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from entities.tradeManager.Position import Position
from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType


class PerpLedger:
    def __init__(self, fee_model, slippage_model):
        self.positions: Dict[str, Position] = defaultdict(Position)
        self.cash_changes: List[Tuple[int, float]] = []
        self.fee_model = fee_model
        self.slippage_model = slippage_model

    # identical to old ingest except recognises FUNDING / LIQUIDATE qty==0
    def ingest(self, events: List[TradeEvent]):
        events.sort(key=lambda e: e.ts)
        for ev in events:
            if ev.event is TradeEventType.FUNDING:
                self.cash_changes.append((ev.ts, ev.meta["funding_cash"]))
                continue

            slip = self.slippage_model(ev)
            fee = self.fee_model(ev)
            px = ev.price * (1 + slip + fee * (1 if ev.qty > 0 else -1))
            notional = px * ev.qty * -1
            self.cash_changes.append((ev.ts, notional))
            self.positions[ev.meta["symbol"]].apply(ev)

    def pop_cash_delta(self) -> float:
        total = sum(c for _, c in self.cash_changes)
        self.cash_changes.clear()
        return total

    # unrealised PnL still delegated to PortfolioManager mark-to-market
