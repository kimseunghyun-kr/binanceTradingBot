# app/services/marketDataService/adapters/binance_provider.py

from __future__ import annotations
from asyncio import get_running_loop
from datetime import datetime
from typing import Callable, Optional, List

import pandas as pd
from redis import Redis
from pymongo.database import Database as SyncDatabase

from app.marketDataApi.binance import fetch_candles, get_valid_binance_symbols


class BinanceProvider:
    """Adapter that conforms to IDataProvider, with injected dependencies."""
    name = "Binance"

    def __init__(
        self,
        redis_client: Redis,
        mongo_sync: SyncDatabase,
        fetch_fn: Callable[[str, str, int, Optional[int]], pd.DataFrame] = fetch_candles,
        symbols_fn: Callable[[], set[str]] = get_valid_binance_symbols,
    ):
        self._redis = redis_client
        self._mongo_sync = mongo_sync
        self._fetch_fn = fetch_fn
        self._symbols_fn = symbols_fn

    async def list_symbols(self) -> List[str]:
        """List all valid symbols via injected symbols_fn."""
        loop = get_running_loop()
        # Run the sync symbols_fn in a thread to avoid blocking
        return await loop.run_in_executor(None, lambda: list(self._symbols_fn()))

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data, then cache to Redis and persist to MongoDB.
        """
        loop = get_running_loop()
        start_ms = int(start.timestamp() * 1000) if start else None

        # 1) Raw HTTP fetch
        df = await loop.run_in_executor(
            None,
            self._fetch_fn,
            symbol,
            interval,
            limit,
            start_ms
        )

        # 2) Cache in Redis
        try:
            cache_key = f"{symbol}:{interval}:{start_ms}:{limit}"
            self._redis.set(cache_key, df.to_json(), ex=3600)
        except Exception:
            pass

        # 3) Persist to MongoDB
        try:
            coll = self._mongo_sync["candles"]
            for row in df.to_dict(orient="records"):
                coll.update_one(
                    {"symbol": symbol, "interval": interval, "open_time": row["open_time"]},
                    {"$set": row},
                    upsert=True,
                )
        except Exception:
            pass

        return df