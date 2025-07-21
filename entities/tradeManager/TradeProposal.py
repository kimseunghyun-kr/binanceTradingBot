# entities/tradeProposal/TradeProposal.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing      import List, Sequence, Callable

import pandas as pd

from .TradeEventType import TradeEventType
from .TradeMeta      import TradeMeta
from .TradeEvent     import TradeEvent


@dataclass
class TradeProposal:
    """
    Pure container that converts a strategy signal into an ordered
    list of TradeEvents.  **Prices are raw** – the ledger will apply
    fee & slippage exactly once.

    Attributes
    ----------
    meta       : TradeMeta        – immutable per-trade metadata
    detail_df  : pd.DataFrame     – higher-resolution candles used to
                                    evaluate DCA and exit conditions
    """
    meta: TradeMeta
    detail_df: pd.DataFrame
    _events: List[TradeEvent] = field(default_factory=list, init=False)

    # ------------------------------------------------------------------ #
    # PUBLIC
    # ------------------------------------------------------------------ #
    def build_events(
        self,
        *,
        add_pct: float = 5.0,          # DCA distance (% from filled entry)
        execution_delay_bars: int = 0  # skip N candles before first fill
    ) -> Sequence[TradeEvent]:
        """
        Return an **ordered** list of TradeEvent objects.

        Side-effect: caches the list on first build so subsequent
        calls are O(1).
        """
        if self._events:                       # idempotent guard
            return self._events

        if self.detail_df.empty:
            return self._events                # keep empty

        df  = self.detail_df.reset_index(drop=True)
        idx0 = execution_delay_bars
        first_candle = df.iloc[idx0]

        # -------------------------------------------------------------- #
        # 1) Determine execution price for initial fill (RAW price)
        # -------------------------------------------------------------- #
        if self.meta.direction == "LONG":
            entry_px = min(first_candle["open"], self.meta.entry_price)
            init_qty =  self.meta.size
        else:
            entry_px = max(first_candle["open"], self.meta.entry_price)
            init_qty = -self.meta.size

        base_meta = {
            "symbol"       : self.meta.symbol,
            "orig_entry_ts": self.meta.entry_time,
            "orig_entry_px": self.meta.entry_price,
        }

        self._events.append(
            TradeEvent(
                ts   = int(first_candle["open_time"]),
                price= float(entry_px),         # RAW price
                qty  = init_qty,
                event= TradeEventType.OPEN,
                meta = {**base_meta, "leg": "INIT"},
            )
        )

        # -------------------------------------------------------------- #
        # 2) Optional single DCA leg
        # -------------------------------------------------------------- #
        if add_pct > 0:
            if self.meta.direction == "LONG":
                dca_price  = entry_px * (1 - add_pct / 100)   # cheaper
                dca_hit    = lambda c: c["low"]  <= dca_price
                dca_qty    =  self.meta.size
            else:
                dca_price  = entry_px * (1 + add_pct / 100)   # dearer
                dca_hit    = lambda c: c["high"] >= dca_price
                dca_qty    = -self.meta.size

            for _, candle in df.iloc[idx0:].iterrows():
                if dca_hit(candle):
                    self._events.append(
                        TradeEvent(
                            ts   = int(candle["open_time"]),
                            price= float(dca_price),          # RAW
                            qty  = dca_qty,
                            event= TradeEventType.OPEN,
                            meta = {**base_meta, "leg": "DCA"},
                        )
                    )
                    break  # only one DCA leg

        # -------------------------------------------------------------- #
        # 3) Exit – first TP or SL that triggers
        # -------------------------------------------------------------- #
        tp_px, sl_px = self._calc_tp_sl()

        total_size = sum(ev.qty for ev in self._events)  # signed
        exit_qty   = -total_size                         # flatten to zero

        def _append_exit(ts: int, px: float, label: str):
            self._events.append(
                TradeEvent(
                    ts   = ts,
                    price= float(px),                     # RAW
                    qty  = exit_qty,
                    event= TradeEventType.CLOSE,
                    meta = {**base_meta, "exit": label},
                )
            )

        for _, candle in df.iloc[idx0:].iterrows():
            ts_now = int(candle["open_time"])

            if self.meta.direction == "LONG":
                if candle["high"] >= tp_px:              # TP first
                    _append_exit(ts_now, tp_px, "TP")
                    break
                if candle["low"]  <= sl_px:              # SL first
                    _append_exit(ts_now, sl_px, "SL")
                    break
            else:  # SHORT
                if candle["low"]  <= tp_px:
                    _append_exit(ts_now, tp_px, "TP")
                    break
                if candle["high"] >= sl_px:
                    _append_exit(ts_now, sl_px, "SL")
                    break

        return self._events

    # ------------------------------------------------------------------ #
    # PRIVATE
    # ------------------------------------------------------------------ #
    def _calc_tp_sl(self) -> tuple[float, float]:
        """
        Returns (tp_price, sl_price).

        Current implementation just echoes the values that the strategy
        placed inside TradeMeta, but you can plug in more sophisticated
        laddering here without touching other modules.
        """
        return float(self.meta.tp_price), float(self.meta.sl_price)

    # ------------------------------------------------------------------ #
    # Legacy alias – PortfolioManager still calls realise()
    # ------------------------------------------------------------------ #
    def realize(self, *args, **kwargs) -> List[TradeEvent]:
        """Back-compat wrapper."""
        return list(self.build_events(*args, **kwargs))
