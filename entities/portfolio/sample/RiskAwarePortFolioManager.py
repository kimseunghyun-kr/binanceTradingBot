from entities.portfolio.BasePortfolioManager import BasePortfolioManager


class RiskAwarePortfolioManager(BasePortfolioManager):
    max_notional_per_trade = 50_000  # example caps, USD
    max_total_notional = 200_000

    def total_notional(self) -> float:
        """Sum of |qty| × mark price over all open positions."""
        return sum(abs(p.qty) * p.avg_px for p in self.positions.values())

    # override ----------------------------------------------------------------
    def risk_ok(self, proposal) -> bool:
        notional = abs(proposal.meta.entry_price * proposal.meta.size)

        # per-trade cap
        if notional > self.max_notional_per_trade:
            return False

        # portfolio-level cap
        if self.total_notional() + notional > self.max_total_notional:
            return False

        return True
