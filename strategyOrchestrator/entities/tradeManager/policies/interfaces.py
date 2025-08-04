from typing import Protocol, List, runtime_checkable

from strategyOrchestrator.entities.tradeManager.FillRecord import FillRecord
from strategyOrchestrator.entities.tradeManager.TradeEvent import TradeEvent


# ───────────────────────────────── fill policy ───────────────────────── #
@runtime_checkable
class FillPolicy(Protocol):
    """
        Decide how an incoming TradeEvent is filled against the order-book.
        Implementations must yield one or more FillRecord objects whose
        qty sum equals the *signed* TradeEvent.qty.
    """
    def fill(
        self,
        event: TradeEvent,
        book: "OrderBookSlice | None" = None,
    ) -> List[FillRecord]: ...