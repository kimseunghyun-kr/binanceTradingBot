from typing import Protocol, List

from entities.tradeManager.FillRecord import FillRecord
from entities.tradeManager.TradeEvent import TradeEvent


# ───────────────────────────────── fill policy ───────────────────────── #

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