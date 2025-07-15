from typing import Dict, Any, Optional, Callable

from entities.portfolio.TradeLogEntry import TradeLogEntry
from entities.portfolio.fees.fees import static_fee_model
from entities.tradeProposal.TradeProposal import TradeProposal


class BasePortfolioManager:
    """
    Portfolio Manager abstract base class.
    - Accepts lazy TradeProposals.
    - Tracks cash, positions, trade log, equity curve.
    - Modular: add slippage, fees, position sizing, risk logic.
    """
    def __init__(self, initial_cash=100_000, max_positions=5, fee_model=None, slippage_model=None):
        self.cash = initial_cash
        self.max_positions = max_positions
        self.positions = {}  # symbol -> list of active positions, to allow multi-leg
        self.trade_log = []
        self.equity_curve = []
        self.fee_model = fee_model or static_fee_model
        self.slippage_model = slippage_model or (lambda meta, action: 0.0)
        self._timestamp = None

    def can_open(self, symbol, entry_price, size):
        """
        Basic constraints: not over max positions and enough cash.
        Extendable for more complex logic.
        """
        total_positions = sum(len(v) for v in self.positions.values())
        return total_positions < self.max_positions and self.cash >= entry_price * size

    def try_execute(self, trade_proposal: 'TradeProposal', add_buy_pct=5.0):
        """
        Receives a TradeProposal object, makes allocation decision, executes if allowed.
        Only realizes trade outcome after accepting.
        """
        # Only look at entry info here—outcome is lazy
        symbol = trade_proposal.symbol
        entry_time = trade_proposal.entry_time
        entry_price = trade_proposal.entry_price
        size = trade_proposal.size
        meta = trade_proposal.meta
        fee = self.fee_model(meta, "entry")
        slippage = self.slippage_model(meta, "entry")

        if not self.can_open(symbol, entry_price, size):
            return False

        # Reserve capital, add position
        if symbol not in self.positions:
            self.positions[symbol] = []
        self.positions[symbol].append({
            'entry_time': entry_time,
            'entry_price': entry_price,
            'size': size,
        })
        self.cash -= entry_price * size

        # Realize trade outcome for accepted trade only
        outcome_trades = trade_proposal.realize(add_buy_pct=add_buy_pct, fee=fee, slippage=slippage)
        if outcome_trades is None:
            # If the trade simulation failed, release the reserved capital
            self.cash += entry_price * size
            self.positions[symbol].pop()
            if not self.positions[symbol]:
                del self.positions[symbol]
            return False

        # Close all sub-trades on outcome
        for trade in outcome_trades:
            self.close_position(symbol, trade['entry_time'], trade['exit_time'], trade['entry_price'], trade['exit_price'], size, trade)
        return True

    def close_position(
            self,
            symbol: str,
            entry_time: int,
            exit_time: int,
            entry_price: float,
            exit_price: float,
            size: float,
            trade: Dict[str, Any],
            extra_analytics_fn: Optional[Callable[[Dict[str, Any], "BasePortfolioManager"], None]] = None,
    ) -> None:
        """
        Close an open position, return capital, log trade, and update portfolio equity.

        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT").
            entry_time (int): Timestamp of entry (e.g., ms since epoch).
            exit_time (int): Timestamp of exit.
            entry_price (float): Entry price of the trade.
            exit_price (float): Exit price of the trade.
            size (float): Position size (e.g., number of contracts or lots).
            trade (dict): Trade result metadata (must contain at least 'result' and 'exit_type').
            extra_analytics_fn (callable, optional): Optional callback for per-trade analytics or side-effects.
                Should accept (trade_log_entry, portfolio_manager) as arguments.

        Returns:
            None

        Side Effects:
            - Removes the closed position from active positions.
            - Updates cash balance and appends trade to trade log.
            - Calls mark_to_market to record equity at exit_time.
            - If extra_analytics_fn is given, calls it with the trade log entry and self (the portfolio manager).
        """
        positions_list = self.positions.get(symbol, [])
        for i, pos in enumerate(positions_list):
            if pos['entry_time'] == entry_time and pos['entry_price'] == entry_price:
                positions_list.pop(i)
                break
        if not positions_list:
            self.positions.pop(symbol, None)
        self.cash += exit_price * size
        trade_log_entry = TradeLogEntry.from_args(
            symbol, entry_time, entry_price, exit_time, exit_price, size, trade
        )
        self.trade_log.append(trade_log_entry.__dict__)
        self.mark_to_market({symbol: exit_price}, exit_time)
        if extra_analytics_fn:
            extra_analytics_fn(trade_log_entry, self)

    def mark_to_market(self, current_prices, time):
        # Mark total equity at a given time (cash + market value of open positions)
        equity = self.cash
        for symbol, pos_list in self.positions.items():
            for pos in pos_list:
                price = current_prices.get(symbol, pos['entry_price'])
                equity += price * pos['size']
        self.equity_curve.append({'time': time, 'equity': equity})
        return equity

    def get_results(self):
        return {
            'trade_log': self.trade_log,
            'final_cash': self.cash,
            'equity_curve': self.equity_curve
        }
