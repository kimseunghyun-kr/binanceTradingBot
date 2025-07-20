# entities/tradeProposal/TradeProposal.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Sequence
import pandas as pd

from .TradeEventType import TradeEventType
from .TradeMeta import TradeMeta
from .TradeEvent import TradeEvent

@dataclass
class TradeProposal:
    meta: TradeMeta
    detail_df: pd.DataFrame
    _events: List[TradeEvent] = field(default_factory=list, init=False)

    def build_events(
            self,
            add_pct: float = 5.0,  # works for both long & short
            fee: float = 0.0,
            slippage: float = 0.0,
            execution_delay_bars: int = 0,
    ) -> Sequence[TradeEvent]:
        if self._events:  # idempotent
            return self._events

        df = self.detail_df
        if df.empty:
            return []

        idx0 = execution_delay_bars
        first_candle = df.iloc[idx0]

        # ---------- ENTRY PRICE ----------
        if self.meta.direction == "LONG":
            px0 = min(first_candle["open"], self.meta.entry_price)
        else:  # SHORT → want to sell as high as possible
            px0 = max(first_candle["open"], self.meta.entry_price)
        px0 *= (1 + slippage + fee)

        # ---------- INITIAL FILL ----------
        init_qty = self.meta.size if self.meta.direction == "LONG" else -self.meta.size
        self._events.append(
            TradeEvent(ts=int(first_candle["open_time"]),
                       price=px0,
                       qty=init_qty,
                       event=TradeEventType.OPEN)
        )

        # ---------- OPTIONAL DCA LEG ----------
        if self.meta.direction == "LONG":
            add_price = px0 * (1 - add_pct / 100)  # cheaper
            hit_check = lambda c: c["low"] <= add_price
            add_qty = self.meta.size
        else:  # SHORT
            add_price = px0 * (1 + add_pct / 100)  # higher
            hit_check = lambda c: c["high"] >= add_price
            add_qty = -self.meta.size

        for _, candle in df.iloc[idx0:].iterrows():
            if hit_check(candle):
                self._events.append(
                    TradeEvent(ts=int(candle["open_time"]),
                               price=add_price * (1 + slippage + fee),
                               qty=add_qty,
                               event=TradeEventType.OPEN,
                               meta={"leg": "DCA"})
                )
                break  # only one extra leg for now

        # ---------- EXIT (TP / SL) ----------
        tp, sl = self._calc_tp_sl(px0)
        # total size currently open (absolute value)
        total_size = self.meta.size * (2 if len(self._events) == 2 else 1)

        for _, candle in df.iloc[idx0:].iterrows():
            if self.meta.direction == "LONG":
                # take-profit: price rallied
                if candle["high"] >= tp:
                    self._events.append(
                        TradeEvent(int(candle["open_time"]), tp, -total_size,
                                   TradeEventType.CLOSE, {"exit": "TP"}))
                    break
                # stop-loss: price fell
                if candle["low"] <= sl:
                    self._events.append(
                        TradeEvent(int(candle["open_time"]), sl, -total_size,
                                   TradeEventType.CLOSE, {"exit": "SL"}))
                    break
            else:  # SHORT  ⏪ reverse comparisons & qty sign
                # take-profit: price dropped
                if candle["low"] <= tp:
                    self._events.append(
                        TradeEvent(int(candle["open_time"]), tp, total_size,
                                   TradeEventType.CLOSE, {"exit": "TP"}))
                    break
                # stop-loss: price rose
                if candle["high"] >= sl:
                    self._events.append(
                        TradeEvent(int(candle["open_time"]), sl, total_size,
                                   TradeEventType.CLOSE, {"exit": "SL"}))
                    break

        return self._events

    # --------------------------------------------------------
    def _calc_tp_sl(self, entry_px: float) -> tuple[float,float]:
        return (self.meta.tp_price, self.meta.sl_price)   # plug in smarter logic here

    # convenience so portfolioManager can still call realize()
    def realize(self, *a, **kw) -> List[TradeEvent]:
        return list(self.build_events(*a, **kw))
