# entities/portfolio/FillRecord.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any

from entities.tradeManager.TradeEventType import TradeEventType


@dataclass(frozen=True, slots=True)
class FillRecord:
    """
    Immutable execution record produced by the TransactionManager.
    """
    ts:         int
    symbol:     str
    side:       str                 # 'BUY' or 'SELL'
    qty:        float               # signed (+ buy, – sell)
    raw_price:  float               # price in TradeEvent
    exec_price: float               # after slippage
    fee_cash:   float               # commission in quote currency
    event:      TradeEventType
    meta:       Dict[str, Any]
