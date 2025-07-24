from __future__ import annotations
from datetime import datetime
from typing import Sequence, Protocol, TypedDict

import pandas as pd

class IDataProvider(Protocol):
    name: str
    async def list_symbols(self) -> list[str]: ...
    async def fetch_ohlcv(self, symbol: str, interval: str, start: datetime | None = None, **kw) -> pd.DataFrame: ...

class DataService:
    def __init__(self, providers: Sequence[IDataProvider]):
        self.providers = {p.name: p for p in providers}

    # Symbol filter --------------------------------------------------------------------
    async def filter_symbols(
        self,
        *,
        market_cap_min: float | None = None,
        market_cap_max: float | None = None,
        provider: str = "CMC",
    ) -> list[str]:
        symbols = await self.providers[provider].list_symbols()
        # (market_cap filters already applied by CMC helper ‑ no extra work here)
        return symbols

    # OHLCV -----------------------------------------------------------------------------
    async def get_ohlcv(self, symbol: str, interval: str, start: datetime | None = None, **kw) -> pd.DataFrame:
        return await self.providers["Binance"].fetch_ohlcv(symbol, interval, start=start, **kw)