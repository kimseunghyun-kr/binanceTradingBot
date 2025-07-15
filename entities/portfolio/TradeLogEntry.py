from dataclasses import dataclass

@dataclass
class TradeLogEntry:
    symbol: str
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    size: float
    pnl: float
    return_pct: float
    result: str
    exit_type: str
    direction: str = "LONG"

    @classmethod
    def from_args(cls, symbol, entry_time, entry_price, exit_time, exit_price, size, trade):
        direction = trade.get('direction', 'LONG')
        if direction == 'LONG':
            pnl = (exit_price - entry_price) * size
            return_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl = (entry_price - exit_price) * size
            return_pct = (entry_price - exit_price) / entry_price * 100
        return cls(
            symbol, entry_time, entry_price, exit_time, exit_price, size,
            pnl, return_pct,
            trade.get('result', ''),
            trade.get('exit_type', ''),
            direction
        )
