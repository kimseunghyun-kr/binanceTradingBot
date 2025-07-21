# entities/portfolio/BasePortfolioManager.py
from __future__ import annotations

import heapq
from typing import Dict, Any, Callable, List, Optional

from entities.portfolio.TradeLogEntry import TradeLogEntry
from entities.portfolio.fees.fees     import static_fee_model
from entities.tradeManager.FillRecord import FillRecord
from entities.tradeManager.TradeProposal  import TradeProposal
from entities.tradeManager.TradeEvent      import TradeEvent
from entities.tradeManager.TransactionLedger import TransactionManager


class BasePortfolioManager:
    """
    Event-driven portfolio:

    • Enqueue TradeEvents produced by TradeProposals
    • At each bar flush due events into TransactionManager
    • Keep cash / equity curve / trade-log
    """

    # ────────────────────────────────────────────────────────────────
    # INIT
    # ────────────────────────────────────────────────────────────────
    def __init__(
        self,
        initial_cash:    float = 100_000,
        max_positions:   int   = 5,
        sizing_model:    Optional[Callable[[Any, str], float]] = None,
        fee_model:       Optional[Callable[[TradeEvent], float]] = None,
        slippage_model:  Optional[Callable[[TradeEvent], float]] = None,
    ):
        self.cash            = initial_cash
        self.max_positions   = max_positions
        self.sizing_model    = sizing_model      or (lambda meta, act: 1.0)
        self.fee_model       = fee_model         or static_fee_model
        self.slippage_model  = slippage_model    or (lambda ev: 0.0)

        # Execution ledger
        self.tm = TransactionManager(self.fee_model, self.slippage_model)

        # Min-heap of future TradeEvents
        self._event_q: List[TradeEvent] = []
        heapq.heapify(self._event_q)

        # Outputs
        self._trade_log:    List[dict] = []      # list of dicts
        self.equity_curve:  List[dict] = []

    # ────────────────────────────────────────────────────────────────
    # INTERNAL
    # ────────────────────────────────────────────────────────────────
    def _open_legs(self) -> int:
        """Count current open position *legs* (non-zero Position objects)."""
        return sum(1 for pos in self.tm.positions.values() if pos.qty != 0)

    def _risk_ok(self, _meta) -> bool:
        """Risk-check stub – extend with exposure, VAR, etc."""
        return True

    # ────────────────────────────────────────────────────────────────
    # PUBLIC – CALLED BY ORCHESTRATOR
    # ────────────────────────────────────────────────────────────────
    def try_execute(
        self,
        proposal: TradeProposal,
        *,
        now_ts:  int | None = None,
        add_pct: float      = 5.0,
    ) -> bool:
        """
        Validate & enqueue a TradeProposal.

        Only OPEN events occurring *now_ts* count toward max_positions.
        """
        now_ts = now_ts or proposal.meta.entry_time

        if not self._risk_ok(proposal.meta):
            return False

        events = proposal.build_events(add_pct=add_pct)
        if not events:
            return False

        # capacity check
        opens_now = sum(1 for e in events if e.is_entry and e.ts == now_ts)
        if self._open_legs() + opens_now > self.max_positions:
            return False

        # optional sizing model (multiplicative on entry qty)
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

    # ----------------------------------------------------------------
    def on_bar(self, ts: int, mark_prices: Dict[str, float]) -> None:
        """
        Process all events with timestamp ≤ ts, update cash & equity.
        """
        # 1️⃣ Ingest events due up to this bar
        while self._event_q and self._event_q[0].ts <= ts:
            ev = heapq.heappop(self._event_q)
            pre_fills = len(self.tm.get_fills())           # before ingest
            self.tm.ingest([ev])
            post_fills = self.tm.get_fills()

            # If this was an EXIT we record a TradeLogEntry using the
            # *actual* exec price from the corresponding FillRecord.
            if ev.is_exit and post_fills:
                fill: FillRecord = post_fills[-1]          # latest fill
                self._log_exit(ev, fill.exec_price)

        # 2️⃣ Realised cash
        self.cash += self.tm.pop_cash_delta()

        # 3️⃣ Mark-to-market
        equity = self.cash + self.tm.unrealised_pnl(mark_prices)
        self.equity_curve.append({"time": ts, "equity": equity})

    # ────────────────────────────────────────────────────────────────
    # LOGGING
    # ────────────────────────────────────────────────────────────────
    def _log_exit(self, ev: TradeEvent, exec_px: float):
        tle = TradeLogEntry.from_args(
            symbol      = ev.meta.get("symbol", "UNK"),
            entry_time  = ev.meta.get("orig_entry_ts", ev.ts),
            entry_price = ev.meta.get("orig_entry_px", ev.price),
            exit_time   = ev.ts,
            exit_price  = exec_px,                       # actual
            size        = abs(ev.qty),
            trade       = {"exit_type": ev.meta.get("exit", ev.event.name)},
        )
        self._trade_log.append(tle.__dict__)

    # ────────────────────────────────────────────────────────────────
    # RESULTS
    # ────────────────────────────────────────────────────────────────
    def get_results(self) -> dict:
        return {
            "final_cash":  self.cash,
            "trade_log":   self._trade_log,
            "equity_curve":self.equity_curve,
        }
