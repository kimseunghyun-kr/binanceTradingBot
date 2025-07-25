# app/adapters/binance_provider.py
from __future__ import annotations

from asyncio import get_running_loop
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
        loop = get_running_loop()
        start_ms = int(start.timestamp() * 1000) if start else None
        # run sync network call in a thread so we don't block other coroutines
        return await loop.run_in_executor(
            None,  # default ThreadPoolExecutor
            fetch_candles,
            symbol,
            interval,
            limit,
            start_ms,
        )

    async def fetch_funding(self, *a, **kw):
        raise NotImplementedError("Binance spot has no funding; use Perp provider")