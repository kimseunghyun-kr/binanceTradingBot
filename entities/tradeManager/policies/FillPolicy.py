# entities/execution/fill_policy.py
from __future__ import annotations

from typing import Protocol, List

from entities.tradeManager.FillRecord import FillRecord
from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.policies.interfaces import FillPolicy


# --------------------------------------------------------------------- #
# 1) Default “aggressive market” – old behaviour (1:1 fill)
# --------------------------------------------------------------------- #
class AggressiveMarketPolicy(FillPolicy):
    def __init__(self, fee_model, slip_model):
        self._fee_model = fee_model
        self._slip_model = slip_model

    def fill(self, event: TradeEvent, *_):
        slip_pct = self._slip_model(event)
        sign = 1.0 if event.qty > 0 else -1.0
        exec_px = event.price * (1 + sign * slip_pct)

        fee_pct = self._fee_model(event)
        fee_cash = abs(exec_px * event.qty) * fee_pct

        return [FillRecord(
            ts=event.ts,
            symbol=event.meta["symbol"],
            side="BUY" if event.qty > 0 else "SELL",
            qty=event.qty,
            raw_price=event.price,
            exec_price=exec_px,
            fee_cash=fee_cash,
            event=event.event,
            meta=event.meta,
        )]


# --------------------------------------------------------------------- #
# 2) Book-walking VWAP depth policy (toy demo)
# --------------------------------------------------------------------- #
class VWAPDepthPolicy(FillPolicy):
    def __init__(self, depth: int, fee_model, slip_model):
        self.depth = depth
        self.fee_model = fee_model
        self.slip_model = slip_model

    # ------------------------------------------------------------------ #
    def fill(self, event: TradeEvent, book: "OrderBookSlice | None" = None) -> List[FillRecord]:
        """
        Break the TradeEvent into N FillRecords; never mutates `event`.
        """
        fills: list[FillRecord] = []
        remaining = abs(event.qty)  # local mutable counter
        sign = 1.0 if event.qty > 0 else -1.0
        side_str = "BUY" if sign > 0 else "SELL"

        levels = book.levels(side_str.lower())[: self.depth] if book else []

        for px, avail in levels:
            take = min(remaining, avail)
            if take == 0:
                break

            exec_px = px * (1 + sign * self.slip_model(event))
            fee_cash = abs(exec_px * take) * self.fee_model(event)

            fills.append(FillRecord(
                ts=event.ts, symbol=event.meta["symbol"],
                side=side_str, qty=sign * take,
                raw_price=px, exec_price=exec_px,
                fee_cash=fee_cash, event=event.event,
                meta=event.meta | {"book_px": px},
            ))

            remaining -= take
            if remaining <= 0:
                break

        # left-over size filled aggressively at worst px
        if remaining:
            worst_px = levels[-1][0] if levels else event.price
            exec_px = worst_px * (1 + sign * self.slip_model(event))
            fee_cash = abs(exec_px * remaining) * self.fee_model(event)

            fills.append(FillRecord(
                ts=event.ts, symbol=event.meta["symbol"],
                side=side_str, qty=sign * remaining,
                raw_price=worst_px, exec_price=exec_px,
                fee_cash=fee_cash, event=event.event,
                meta=event.meta | {"book_px": worst_px, "overflow": True},
            ))

        return fills
