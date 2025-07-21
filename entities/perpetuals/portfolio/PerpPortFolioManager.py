from __future__ import annotations
from typing import Dict

from entities.perpetuals.contracts.perp_specs import PERP_SPECS
from entities.perpetuals.portfolio.Funding_repository import funding_provider
from entities.perpetuals.portfolio.PerpLedger import PerpLedger
from entities.perpetuals.portfolio.margin import maintenance_margin_usd
from entities.portfolio.BasePortfolioManager import BasePortfolioManager
from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType


class PerpPortfolioManager(BasePortfolioManager):
    """
    Adds funding & margin liquidation to BasePortfolioManager.

    • no external HTTP calls – data read from Mongo only
    • user strategies remain unchanged
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Swap ledger implementation
        self.tm = PerpLedger(self.fee_model, self.slippage_model)

    # --------------------------------------------------------------
    def on_bar(self, ts: int, mark_prices: Dict[str, float]) -> None:
        self._apply_funding(ts, mark_prices)
        self._check_liquidation(ts, mark_prices)
        super().on_bar(ts, mark_prices)   # flush events + equity calc

    # --------------------------------------------------------------
    def _apply_funding(self, ts: int, mark_prices: Dict[str, float]):
        for sym, pos in self.tm.positions.items():
            if pos.qty == 0:
                continue
            spec = PERP_SPECS.get(sym)
            if not spec or ts % spec.funding_intvl:
                continue
            rate = funding_provider.get_rate(sym, ts)
            cash = -pos.qty * pos.avg_px * rate
            ev = TradeEvent(
                ts=ts, price=pos.avg_px, qty=0,
                event=TradeEventType.FUNDING,
                meta={"symbol": sym, "funding_cash": cash},
            )
            self.tm.ingest([ev])

    def _check_liquidation(self, ts: int, mark_prices: Dict[str, float]):
        equity = self.cash + self.tm.unrealised_pnl(mark_prices)
        for sym, pos in self.tm.positions.items():
            if pos.qty == 0:
                continue
            mp   = mark_prices.get(sym, pos.avg_px)
            spec = PERP_SPECS[sym]
            maint= maintenance_margin_usd(sym, pos.qty, mp, spec.mmr)
            if equity < maint:
                ev = TradeEvent(
                    ts=ts, price=mp, qty=-pos.qty,
                    event=TradeEventType.LIQUIDATE,
                    meta={"symbol": sym},
                )
                self.tm.ingest([ev])
