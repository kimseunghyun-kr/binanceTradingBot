from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType


class Position:
    """
    Tracks net quantity, VWAP and realised PnL for a single symbol.
    `qty` is signed (+ long, − short).
    """
    def __init__(self):
        self.qty           = 0.0
        self.avg_px        = 0.0
        self.realized_pnl  = 0.0

    # ------------------------------------------------------------------ #
    def apply(self, e: TradeEvent):
        # 1) SIDE-FLIP OR REDUCE (sign differs from existing position)
        if self.qty and (self.qty > 0) != (e.qty > 0):
            # qtys of opposite sign → this fill partly or fully closes
            closed_qty   = -min(abs(self.qty), abs(e.qty)) * (1 if self.qty > 0 else -1)
            self.realized_pnl += closed_qty * (e.price - self.avg_px)

            self.qty += e.qty           # signed addition

            # if flip through zero into opposite side, avg_px resets
            if self.qty:
                self.avg_px = e.price    # new side’s entry
            else:
                self.avg_px = 0.0

        # 2) SAME-SIDE INCREASE (typical OPEN / DCA)
        elif e.event == TradeEventType.OPEN:
            # weighted-average price
            new_notional = self.avg_px * self.qty + e.price * e.qty
            self.qty    += e.qty
            self.avg_px  = new_notional / self.qty

        # 3) REDUCE / CLOSE on same side
        elif e.event in {TradeEventType.REDUCE, TradeEventType.CLOSE}:
            closed_qty   = e.qty         # signed: opposite to existing side
            self.realized_pnl += closed_qty * (e.price - self.avg_px)
            self.qty += e.qty
            if self.qty == 0:
                self.avg_px = 0.0
