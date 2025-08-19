# entities/portfolio/BasePortfolioManager.py
from __future__ import annotations

import heapq
from typing import Dict, Any, Callable, List, Optional, Set

from strategyOrchestrator.entities.portfolio.TradeLogEntry import TradeLogEntry
from strategyOrchestrator.entities.portfolio.policies.capacity.CapacityPolicy import CapacityPolicy, LegCapacity
from strategyOrchestrator.entities.portfolio.policies.fees.fees import static_fee_model
from strategyOrchestrator.entities.portfolio.policies.interfaces import SizingModel
from strategyOrchestrator.entities.tradeManager.TradeEvent import TradeEvent
from strategyOrchestrator.entities.tradeManager.TradeProposal import TradeProposal
from strategyOrchestrator.entities.tradeManager.TransactionLedger import TransactionLedger


class BasePortfolioManager:
    """
    Event-driven portfolio manager

    • Enqueue TradeEvents produced by TradeProposals
    • Flush due events into TransactionLedger each bar
    • Keep cash / equity curve / trade-log
    """

    # ──────────────────────────────────────────────────────────────
    # INIT
    # ──────────────────────────────────────────────────────────────
    def __init__(
        self,
        initial_cash   : float = 100_000,
        capacity_policy: CapacityPolicy | None = None,
        sizing_model: SizingModel | None = None,
        fee_model      : Optional[Callable[[TradeEvent], float]] = None,
        slippage_model : Optional[Callable[[TradeEvent], float]] = None,
        fill_policy    : Any    = None,     # optional, injected into ledger
    ):
        self.cash           = initial_cash
        self.capacity = capacity_policy or LegCapacity(max_legs=5)
        self.sizing_model   = sizing_model   or (lambda meta, act: 1.0)
        self.fee_model      = fee_model      or static_fee_model
        self.slip_model     = slippage_model or (lambda ev: 0.0)

        self.tm = TransactionLedger(self.fee_model, self.slip_model, fill_policy)

        self._event_q : List[TradeEvent] = []
        heapq.heapify(self._event_q)

        self._trade_log   : List[dict] = []
        self.equity_curve : List[dict] = []

    # ──────────────────────────────────────────────────────────────
    # INTERFACE LAYER – override any you need
    # ──────────────────────────────────────────────────────────────

    def _open_symbols(self) -> Set[str]:
        return {sym for sym, pos in self.tm.positions.items() if pos.qty != 0}

    def _open_legs(self) -> int:
        """Count Position objects with non-zero qty."""
        return sum(1 for p in self.tm.positions.values() if p.qty != 0)

    def _risk_ok(self, meta) -> bool:
        """High-level risk (VAR, leverage, blacklist symbols…)."""
        return True

    # inside BasePortfolioManager._cash_ok
    def _cash_ok(self, entry_px: float, size: float) -> bool:
        required = entry_px * size
        return self.cash >= required

    # Single decision point ------------------------------------------------
    def can_open(
        self,
        proposal   : TradeProposal,
        now_ts     : int,
        first_entry: TradeEvent,
    ) -> bool:
        return (
            self._risk_ok(proposal.meta)
            and self._cash_ok(first_entry.price, abs(first_entry.qty))
            and self.capacity.admit(
                proposal,
                now_ts,
                self._event_q,
                self._open_symbols(),
            )
        )

    # ──────────────────────────────────────────────────────────────
    # PUBLIC – called by orchestrator
    # ──────────────────────────────────────────────────────────────
    def try_execute(
        self,
        proposal: TradeProposal,
        *,
        now_ts: int | None = None,
    ) -> bool:
        now_ts = now_ts or proposal.meta.entry_time
        events = proposal.build_events()
        if not events:
            return False

        first_entry = next((e for e in events if e.is_entry), None)
        if first_entry is None:
            return False

        if not self.can_open(proposal, now_ts, first_entry):
            return False

        # apply portfolio-level sizing
        scale = self.sizing_model(proposal.meta, "entry") or 1.0
        if scale != 1.0:
            events = [
                TradeEvent(e.ts, e.price, e.qty * scale, e.event, dict(e.meta))
                if e.is_entry else e
                for e in events
            ]

        for ev in events:
            heapq.heappush(self._event_q, ev)
        return True

    # ---------------------------------------------------------------------
    def on_bar(self, ts: int, mark_prices: Dict[str, float]) -> None:
        # 1️⃣ ingest due events
        while self._event_q and self._event_q[0].ts <= ts:
            ev = heapq.heappop(self._event_q)
            pre = len(self.tm.get_fills())
            self.tm.ingest([ev])
            post = self.tm.get_fills()

            if ev.is_exit and post:
                self._log_exit(ev, post[-1].exec_price)

        # 2️⃣ realised cash
        self.cash += self.tm.pop_cash_delta()

        # 3️⃣ mark-to-market
        equity = self.cash + self.tm.unrealised_pnl(mark_prices)
        self.equity_curve.append({"time": ts, "equity": equity})

    # ---------------------------------------------------------------------
    def _log_exit(self, ev: TradeEvent, exec_px: float):
        tle = TradeLogEntry.from_args(
            symbol      = ev.meta.get("symbol", "UNK"),
            entry_time  = ev.meta.get("orig_entry_ts", ev.ts),
            entry_price = ev.meta.get("orig_entry_px", ev.price),
            exit_time   = ev.ts,
            exit_price  = exec_px,
            size        = abs(ev.qty),
            trade       = {"exit_type": ev.meta.get("exit", ev.event.name)},
        )
        self._trade_log.append(tle.__dict__)

    # ---------------------------------------------------------------------
    def get_results(self) -> dict:
        return {
            "final_cash"   : self.cash,
            "trade_log"    : self._trade_log,
            "equity_curve" : self.equity_curve,
        }
