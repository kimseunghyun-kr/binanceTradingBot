# app/services/marketDataService/adapters/binance_provider.py

from __future__ import annotations

from asyncio import get_running_loop
from datetime import datetime
from typing import Callable, Optional, List

import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from app.marketDataApi.binance import fetch_candles, get_valid_binance_symbols


class BinanceProvider:
    """Adapter that conforms to IDataProvider, with injected async Mongo and sync Redis clients."""
    name = "Binance"

    def __init__(
        self,
        redis_client: Redis,
        mongo_async: AsyncIOMotorDatabase,
        fetch_fn: Callable[[str, str, int, Optional[int]], pd.DataFrame] = fetch_candles,
        symbols_fn: Callable[[], set[str]] = get_valid_binance_symbols,
    ):
        self._redis = redis_client
        self._mongo = mongo_async
        self._fetch = fetch_fn
        self._symbols = symbols_fn

    async def list_symbols(self) -> List[str]:
        """List all valid symbols via injected symbols_fn, run in thread."""
        loop = get_running_loop()
        return await loop.run_in_executor(None, lambda: list(self._symbols()))

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data (HTTP), cache in Redis, and persist asynchronously to MongoDB.
        """
        loop = get_running_loop()
        start_ms = int(start.timestamp() * 1000) if start else None

        # 1) Raw HTTP fetch in thread
        df: pd.DataFrame = await loop.run_in_executor(
            None,
            self._fetch,
            symbol,
            interval,
            limit,
            start_ms
        )

        # 2) Cache in Redis (sync)
        try:
            cache_key = f"{symbol}:{interval}:{start_ms}:{limit}"
            await self._redis.set(cache_key, df.to_json(), ex=3600)
        except Exception:
            pass

        # 3) Persist to MongoDB (async)
        try:
            coll = self._mongo["candles"]
            # upsert each document
            for row in df.to_dict(orient="records"):
                await coll.update_one(
                    {"symbol": symbol, "interval": interval, "open_time": row["open_time"]},
                    {"$set": row},
                    upsert=True,
                )
        except Exception:
            pass

        return df
