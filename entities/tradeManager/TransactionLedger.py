# entities/portfolio/TransactionLedger.py
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List

from FillRecord import FillRecord
from Position import Position
from entities.tradeManager.policies.FillPolicy import FillPolicy, AggressiveMarketPolicy
from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType


class TransactionLedger:
    """
    Deterministic cash & position ledger with pluggable execution model.

    Workflow
    --------
    1. `PortfolioManager` passes a *time-sorted* list of TradeEvents.
    2. Injected `FillPolicy` converts each TradeEvent → 1‒N FillRecords
       (applying *its* own fee / slippage logic).
    3. `_apply_fill()` books cash, updates Position, stores FillRecord.
    """

    # ------------------------------------------------------------------ #
    # INIT
    # ------------------------------------------------------------------ #
    def __init__(
            self,
            fee_model: Callable[[TradeEvent], float],
            slippage_model: Callable[[TradeEvent], float],
            fill_policy: FillPolicy | None = None,
    ):
        # live positions keyed by symbol
        self.positions: Dict[str, Position] = defaultdict(Position)

        # [(ts, cash_delta)]   – negative = cash out, positive = in
        self._cash_log: List[tuple[int, float]] = []

        # analytics
        self._fills: List[FillRecord] = []

        # pricing models
        self._fee_model = fee_model
        self._slip_model = slippage_model

        # policy that performs the slicing **and** cost application
        self._fill_policy: FillPolicy = (
                fill_policy or AggressiveMarketPolicy(fee_model, slippage_model)
        )

    # ------------------------------------------------------------------ #
    # PUBLIC API
    # ------------------------------------------------------------------ #
    def ingest(self, events: List[TradeEvent]) -> None:
        """
        Book a batch of TradeEvents.  Caller guarantees they’re sorted by `ts`.
        """
        for ev in events:
            for fill in self._fill_policy.fill(ev, book=None):
                self._apply_fill(fill)

    # ------------------------------------------------------------------ #
    # CASH & PNL QUERIES
    # ------------------------------------------------------------------ #
    def current_cash_delta(self) -> float:
        """Realised cash Δ since last pop (non-destructive)."""
        return sum(delta for _, delta in self._cash_log)

    def pop_cash_delta(self) -> float:
        """
        Return realised cash Δ **and clear** the log.
        Called once per bar by PortfolioManager.
        """
        total = self.current_cash_delta()
        self._cash_log.clear()
        return total

    def unrealised_pnl(self, mark_prices: Dict[str, float]) -> float:
        """
        Mark-to-market PnL given `mark_prices` (symbol → last price).
        """
        pnl = 0.0
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            mark = mark_prices.get(sym, pos.avg_px)  # fallback: avg_px
            pnl += pos.qty * (mark - pos.avg_px)
        return pnl

    def get_fills(self) -> List[FillRecord]:
        """Expose immutable fills list for analytics / trade-log."""
        return list(self._fills)

    # ------------------------------------------------------------------ #
    # INTERNAL
    # ------------------------------------------------------------------ #
    def _apply_fill(self, fill: FillRecord) -> None:
        """
        Book a single FillRecord:
          • cash ledger
          • position object
          • analytics store
        """
        # ---- cash delta -------------------------------------------------
        if fill.qty == 0 and fill.event.name == "FUNDING":
            cash_delta = -fill.fee_cash  # funding fee already signed
        else:
            cash_delta = -fill.exec_price * fill.qty - fill.fee_cash

        self._cash_log.append((fill.ts, cash_delta))

        # ---- position update -------------------------------------------
        symbol = fill.symbol

        # Reuse Position.apply() by wrapping fill as a pseudo-TradeEvent
        pseudo_ev = TradeEvent(
            ts=fill.ts,
            price=fill.exec_price,
            qty=fill.qty,
            event=fill.event or TradeEventType.OPEN,
            meta=fill.meta,
        )
        self.positions[symbol].apply(pseudo_ev)

        # ---- analytics store -------------------------------------------
        self._fills.append(fill)
