# app/adapters/binance_provider.py
from __future__ import annotations
from datetime import datetime

import pandas as pd

from app.marketDataApi.binance import fetch_candles, get_valid_binance_symbols

class BinanceProvider:
    """Adapter that conforms to IDataProvider."""

    name = "Binance"

    async def list_symbols(self) -> list[str]:
        # could be async but helper is sync ⇒ run in loop’s executor if needed
        return list(get_valid_binance_symbols())

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        start_ms = int(start.timestamp() * 1000) if start else None
        return fetch_candles(symbol, interval, limit=limit, start_time=start_ms)

    async def fetch_funding(self, *a, **kw):
        raise NotImplementedError("Binance spot has no funding; use Perp provider")