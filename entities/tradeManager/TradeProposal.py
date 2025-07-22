# entities/tradeProposal/TradeProposal.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Union, Callable, Optional

import pandas as pd

from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType
from entities.tradeManager.TradeMeta import TradeMeta
from entities.tradeManager.orders.OrderLeg import OrderLeg

# --------------------------------------------------------------------------- #
# TradeProposal:  ✔ multi-leg, ✔ partial-fill, ✔ backward-compatible realise()
# --------------------------------------------------------------------------- #
Timestamp = Union[int, float]  # unix ms / sec - doesn’t matter here


@dataclass
class TradeProposal:
    """
    A *declarative plan* consisting of one or more OrderLeg objects.
    `build_events()` turns that plan into a chronologically-sorted list
    of TradeEvents **with raw (pre-fee, pre-slippage) prices**.

    Parameters
    ----------
    meta       : immutable details that never change for the life of the trade
    legs       : list[OrderLeg]  – scale-in / scale-out instructions
    detail_df  : high-resolution candles needed to evaluate triggers
    """
    meta: TradeMeta
    legs: List[OrderLeg]
    detail_df: pd.DataFrame

    _crossing_policy: str | None = "prefer_sl"
    _exit_resolver: Callable[[pd.Series, float, float, str], Optional[dict]] | None = None

    _events: List[TradeEvent] = field(default_factory=list, init=False)

    # ------------------------------------------------------------------ #
    # PUBLIC
    # ------------------------------------------------------------------ #
    def build_events(self) -> Sequence[TradeEvent]:
        """
        Materialise the OrderLeg plan into executable TradeEvents.
        Result is cached so multiple calls are O(1).
        """
        if self._events or self.detail_df.empty or not self.legs:
            return self._events

        df = self.detail_df.reset_index(drop=True)
        open_legs = self.legs.copy()  # legs yet to be filled

        # ---- iterate through candles, trigger legs when their condition is met
        for idx, candle in df.iterrows():
            ts = int(candle["open_time"])

            # iterate over a *copy* so we can safely remove while iterating
            for leg in open_legs[:]:
                if self._triggered(idx, ts, candle, leg.when):
                    price = self._resolve_price(candle, leg.px)
                    signed_qty = leg.qty if leg.side == "BUY" else -leg.qty

                    self._events.append(
                        TradeEvent(
                            ts=ts,
                            price=float(price),
                            qty=signed_qty,
                            event=TradeEventType.OPEN,
                            meta={
                                "symbol": self.meta.symbol,
                                "leg": leg.comment or f"leg{idx}",
                                "tif": leg.tif,
                            },
                        )
                    )
                    open_legs.remove(leg)  # remove filled leg

            if not open_legs:  # all legs filled ⇒ stop early
                break

        # ------------------------------------------------------------------ #
        # SIMPLE TP / SL EXIT (legacy behaviour – replace / extend as needed)
        # ------------------------------------------------------------------ #
        total_pos = sum(ev.qty for ev in self._events)
        if total_pos:
            exit_qty = -total_pos
            tp_px, sl_px = self.meta.tp_price, self.meta.sl_price

            for _, candle in df[idx:].iterrows():
                ts = int(candle["open_time"])
                hit = self._check_exit(candle, tp_px, sl_px)
                if hit:
                    self._events.append(
                        TradeEvent(
                            ts=ts,
                            price=float(hit["price"]),
                            qty=exit_qty,
                            event=TradeEventType.CLOSE,
                            meta={
                                "symbol": self.meta.symbol,
                                "exit": hit["label"],
                            },
                        )
                    )
                    break

        return self._events

    # ------------------------------------------------------------------ #
    # BACKWARD-COMPAT ALIAS  (PortfolioManager still calls realise())
    # ------------------------------------------------------------------ #
    def realize(self, *_, **__) -> List[TradeEvent]:
        """Alias kept for legacy code; behaves exactly like old realise()."""
        return list(self.build_events())

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    @staticmethod
    def _triggered(idx: int, ts: Timestamp,
                   candle: pd.Series,
                   cond: Union[int, Timestamp, Callable[[pd.Series], bool]]
                   ) -> bool:
        """Return True if `cond` is satisfied at the current candle."""
        if isinstance(cond, int):  # bar-index offset
            return idx >= cond
        if callable(cond):  # predicate on candle
            return bool(cond(candle))
        return ts >= cond  # timestamp

    @staticmethod
    def _resolve_price(candle: pd.Series,
                       px: Union[float, Callable[[pd.Series], float]]
                       ) -> float:
        """Resolve limit/trigger price (callable or static)."""
        return float(px(candle) if callable(px) else px)

    def _check_exit(
            self,
            candle: pd.Series,
            tp_px: float,
            sl_px: float,
    ) -> Optional[dict]:

        # 1️⃣ user-supplied resolver beats presets
        if self._exit_resolver:
            return self._exit_resolver(
                candle, tp_px, sl_px, self.meta.direction
            )

        # 2️⃣ preset crossing policies
        hit_tp = (
            candle["high"] >= tp_px if self.meta.direction == "LONG"
            else candle["low"] <= tp_px
        )
        hit_sl = (
            candle["low"] <= sl_px if self.meta.direction == "LONG"
            else candle["high"] >= sl_px
        )

        if hit_tp and hit_sl:
            mode = self._crossing_policy or "prefer_sl"
            if mode == "prefer_tp":
                return {"price": tp_px, "label": "TP"}
            if mode == "random":
                import random
                return {"price": tp_px, "label": "TP"} if random.random() < 0.5 \
                    else {"price": sl_px, "label": "SL"}
            # default: prefer_sl
            return {"price": sl_px, "label": "SL"}

        if hit_tp:
            return {"price": tp_px, "label": "TP"}
        if hit_sl:
            return {"price": sl_px, "label": "SL"}
        return None

