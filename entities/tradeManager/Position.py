from entities.tradeManager.TradeEvent import TradeEvent
from entities.tradeManager.TradeEventType import TradeEventType


class Position:
    def __init__(self):       # tracks net position & average price
        self.qty   = 0.0
        self.avg_px= 0.0

    def apply(self, e: TradeEvent):
        if e.event == TradeEventType.OPEN:
            new_notional = self.avg_px * self.qty + e.price * e.qty
            self.qty += e.qty
            self.avg_px = 0 if self.qty==0 else new_notional / self.qty
        elif e.event in {TradeEventType.REDUCE, TradeEventType.CLOSE}:
            self.qty += e.qty   # qty is negative for closing long
            if self.qty == 0:
                self.avg_px = 0