from typing import TypedDict


class OHLCV(TypedDict):
    open_time: int  # ms since epoch
    open:  float
    high:  float
    low:   float
    close: float
    volume: float

class FundingRate(TypedDict):
    ts: int
    rate: float
