# entities/portfolio/TransactionLedger.py
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Callable

from .FillRecord import FillRecord
from .Position   import Position
from .TradeEvent import TradeEvent


class TransactionManager:
    """
    Deterministic cash & position ledger.

    • Accepts a time-ordered stream of TradeEvents whose `price`
      is the *raw* market price (no costs baked in).

    • Applies slippage and fee **once** for each fill:
        exec_px  = raw_px × (1 ± slip_pct)
        cashΔ    = -notional ± proceeds - fee_cash

    • Updates per-symbol Position objects and maintains a
      rolling cash-flow log so the PortfolioManager can
      query realised/unrealised PnL at any bar.
    """

    # --------------------------------------------------------------------- #
    # INIT
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        fee_model: Callable[[TradeEvent], float],
        slippage_model: Callable[[TradeEvent], float],
    ):
        # Open positions keyed by symbol
        self.positions: Dict[str, Position] = defaultdict(Position)

        # [(timestamp, cash_delta)]; negative = cash out, positive = in
        self._cash_log: List[tuple[int, float]] = []

        self._fee_model = fee_model        # returns *percentage* (e.g. 0.001)
        self._slip_model = slippage_model  # returns *percentage* (e.g. 0.0005)
        self._fills: List[FillRecord] = []  # NEW

    # --------------------------------------------------------------------- #
    # PUBLIC API
    # --------------------------------------------------------------------- #
    def ingest(self, events: List[TradeEvent]) -> None:
        """
        Apply a batch of TradeEvents.

        The caller must already have sorted them by `ts`
        (PortfolioManager does this when dequeuing per-bar).
        """
        for ev in events:
            # ---- execution price with slippage ---------------------------
            slip_pct = self._slip_model(ev)           # percent (e.g. 0.0005)
            sign     = 1.0 if ev.qty > 0 else -1.0    # buy vs sell
            exec_px  = ev.price * (1.0 + sign * slip_pct)

            # ---- fee on notional ----------------------------------------
            fee_pct   = self._fee_model(ev)           # percent (e.g. 0.001)
            notional  = exec_px * ev.qty              # buy: +, sell: -
            fee_cash  = abs(notional) * fee_pct       # always cash out

            # ---- cash delta ---------------------------------------------
            #   • buy  (+qty): cash out  = -notional - fee
            #   • sell (-qty): cash in   = -notional - fee
            cash_delta = -notional - fee_cash
            self._cash_log.append((ev.ts, cash_delta))

            # ---- update position ----------------------------------------
            symbol        = ev.meta.get("symbol", "UNK")
            self.positions[symbol].apply(ev)

            # keep immutable fill record for analytics
            self._fills.append(
                FillRecord(
                    ts=ev.ts,
                    symbol=symbol,
                    side="BUY" if ev.qty > 0 else "SELL",
                    qty=ev.qty,
                    raw_price=ev.price,
                    exec_price=exec_px,
                    fee_cash=fee_cash,
                    event=ev.event,
                    meta=ev.meta,
                )
            )

    # ------------------------------------------------------------------ #
    # CASH & PnL QUERIES
    # ------------------------------------------------------------------ #
    def current_cash_delta(self) -> float:
        """Return realised cash delta *since the last pop* (non-destructive)."""
        return sum(delta for _, delta in self._cash_log)

    def pop_cash_delta(self) -> float:
        """
        Return realised cash delta and clear the internal log.
        Called by PortfolioManager once per bar.
        """
        total = self.current_cash_delta()
        self._cash_log.clear()
        return total

    def unrealised_pnl(self, mark_prices: Dict[str, float]) -> float:
        """
        Compute MTM PnL using `mark_prices` (symbol → last price).
        """
        pnl = 0.0
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            mark = mark_prices.get(sym, pos.avg_px)   # fallback: last exec px
            pnl += pos.qty * (mark - pos.avg_px)
        return pnl


    def get_fills(self) -> List[FillRecord]:
        """
        expose fills for analytics / trade-log
        :return:
        """
        return list(self._fills)  # copy to keep ledger immutable