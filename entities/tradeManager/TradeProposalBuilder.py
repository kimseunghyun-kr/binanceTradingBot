# entities/tradeProposal/TradeProposalBuilder.py
from __future__ import annotations
from typing import List, Callable, Union
import pandas as pd

from .TradeMeta      import TradeMeta
from .TradeProposal  import TradeProposal
from .orders.OrderLeg import OrderLeg

PriceRef = Union[str, Callable[[pd.Series], float]]


class TradeProposalBuilder:
    # ───────────────────────── init ───────────────────────── #
    def __init__(self, symbol: str, *, size: float = 1.0, direction: str = "LONG"):
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be 'LONG' or 'SHORT'")
        self.symbol    = symbol
        self.size      = float(size)
        self.direction = direction
        self._legs: List[OrderLeg] = []
        self._tp_pct: float | None = None
        self._sl_pct: float | None = None

        # override placeholders (will be applied in build())
        self._entry_price: float | None = None
        self._tp_price   : float | None = None
        self._sl_price   : float | None = None
        self._entry_ts   : int   | None = None

    # ───────────────────────── ladder helper ───────────────────────── #
    def scale_in(self, n: int, start_pct: float, step_pct: float,
                 reference: PriceRef = "open") -> "TradeProposalBuilder":
        ...
        return self

    # ───────────────────────── exit helper ───────────────────────── #
    def bracket_exit(self, *, tp: float, sl: float) -> "TradeProposalBuilder":
        if tp <= 0 or sl <= 0:
            raise ValueError("tp and sl must be positive positive fractions")
        self._tp_pct, self._sl_pct = tp, sl
        return self

    # ───────────────────────── NEW: inject prices from strategy ────── #
    def set_entry_params(self,
                         *,
                         entry_price: float,
                         tp_price: float,
                         sl_price: float,
                         entry_ts : int | None = None) -> "TradeProposalBuilder":
        """
        Store final prices/time chosen by the strategy so we can build an
        immutable TradeMeta without mutating later.
        """
        self._entry_price = float(entry_price)
        self._tp_price    = float(tp_price)
        self._sl_price    = float(sl_price)
        self._entry_ts    = entry_ts
        return self

    # ───────────────────────── build ───────────────────────── #
    def build(self, detail_df: pd.DataFrame) -> TradeProposal:
        if detail_df.empty:
            raise ValueError("detail_df cannot be empty")

        first_candle = detail_df.iloc[0]

        entry_price = (
            self._entry_price if self._entry_price is not None
            else float(first_candle["open"])
        )
        entry_ts = (
            self._entry_ts if self._entry_ts is not None
            else int(first_candle["open_time"])
        )

        if not self._legs:
            self.scale_in(n=1, start_pct=0.0, step_pct=0.0, reference="open")

        tp_price = self._tp_price or entry_price * (1 + (self._tp_pct or 0))
        sl_price = self._sl_price or entry_price * (1 - (self._sl_pct or 0))

        meta = TradeMeta(
            symbol      = self.symbol,
            entry_time  = entry_ts,
            entry_price = entry_price,
            tp_price    = tp_price,
            sl_price    = sl_price,
            size        = self.size,
            direction   = self.direction,
        )
        return TradeProposal(meta=meta, legs=self._legs, detail_df=detail_df)
