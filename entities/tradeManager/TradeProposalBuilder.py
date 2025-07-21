# entities/tradeProposal/TradeProposalBuilder.py
from __future__ import annotations

from typing import List, Callable, Union

import pandas as pd

from TradeMeta import TradeMeta
from TradeProposal import TradeProposal
from entities.tradeManager.orders.OrderLeg import OrderLeg

PriceRef = Union[str, Callable[[pd.Series], float]]  # 'open', 'close', lambda


class TradeProposalBuilder:
    """
    Fluent helper that produces a ready-to-send TradeProposal.

    Typical usage
    -------------
    proposal = (
        TradeProposalBuilder("BTCUSDT", size=2.0, direction="LONG")
        .scale_in(n=4, start_pct=0.00, step_pct=0.005)   # 0 %, 0.5 %, 1 %, 1.5 %
        .bracket_exit(tp=0.10, sl=0.04)                  # +10 %, −4 %
        .build(detail_df)                                # high-res candle slice
    )
    """

    # ------------------------------------------------------------------ #
    def __init__(
            self,
            symbol: str,
            *,
            size: float = 1.0,
            direction: str = "LONG",
    ):
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be 'LONG' or 'SHORT'")
        self.symbol = symbol
        self.size = float(size)
        self.direction = direction
        self._legs: List[OrderLeg] = []
        self._tp: float | None = None
        self._sl: float | None = None

    # ------------------------------------------------------------------ #
    def scale_in(
            self,
            n: int,
            start_pct: float,
            step_pct: float,
            reference: PriceRef = "open",
    ) -> "TradeProposalBuilder":
        """
        Build `n` laddered entry legs.

        Parameters
        ----------
        n          : number of legs (≥ 1)
        start_pct  : first offset  (e.g. 0.00 = at ref price)
        step_pct   : gap between legs (e.g. 0.005 = 0.5 %)
        reference  : 'open' | 'close' | callable(pd.Series)->price
        """
        if n < 1:
            raise ValueError("n must be ≥ 1")

        def _ref_price(candle: pd.Series) -> float:
            return reference(candle) if callable(reference) else candle[reference]

        sign = +1 if self.direction == "LONG" else -1
        leg_qty = abs(self.size) / n

        for k in range(n):
            # For LONG   : negative delta → below market
            # For SHORT  : positive delta → above market
            pct_delta = (start_pct + k * step_pct) * (-sign)

            def _px_fn(c: pd.Series, d=pct_delta) -> float:
                return _ref_price(c) * (1 + d)

            if k == 0:
                when_cond = 0  # execute immediately this bar
            else:
                when_cond = (
                    lambda c, px=_px_fn: c["low"] <= px(c) if self.direction == "LONG"
                    else lambda c, px=_px_fn: c["high"] >= px(c)
                )

            self._legs.append(
                OrderLeg(
                    when=when_cond,
                    side="BUY" if self.direction == "LONG" else "SELL",
                    qty=leg_qty,
                    px=_px_fn,
                    comment=f"scale{k + 1}/{n}",
                )
            )
        return self

    # ------------------------------------------------------------------ #
    def bracket_exit(self, *, tp: float, sl: float) -> "TradeProposalBuilder":
        """
        Attach classical TP / SL *percentages* (0.10 = +10 %, 0.04 = 4 %).
        """
        if tp <= 0 or sl <= 0:
            raise ValueError("tp and sl must be positive fractions (e.g. 0.1)")
        self._tp, self._sl = tp, sl
        return self

    # ------------------------------------------------------------------ #
    def build(self, detail_df: pd.DataFrame) -> TradeProposal:
        """
        Return a ready-to-use TradeProposal.  If you never called
        `.scale_in()`, we create a single “market @ open” leg so the
        proposal is still valid.
        """
        if detail_df.empty:
            raise ValueError("detail_df cannot be empty")

        first_candle = detail_df.iloc[0]
        entry_price = float(first_candle["open"])
        entry_ts = int(first_candle["open_time"])

        # fallback: single leg at open
        if not self._legs:
            self.scale_in(
                n=1,
                start_pct=0.00,
                step_pct=0.00,
                reference="open",
            )

        meta = TradeMeta(
            symbol=self.symbol,
            entry_time=entry_ts,
            entry_price=entry_price,
            tp_price=entry_price * (1 + (self._tp or 0)),
            sl_price=entry_price * (1 - (self._sl or 0)),
            size=self.size,
            direction=self.direction,
        )

        return TradeProposal(
            meta=meta,
            legs=self._legs,
            detail_df=detail_df,
        )
