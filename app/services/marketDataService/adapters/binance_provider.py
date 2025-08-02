# app/services/marketDataService/adapters/binance_provider.py
from __future__ import annotations

from asyncio import get_running_loop
from datetime import datetime
from typing import Callable, Optional, List

import pandas as pd
from celery.utils.log import get_task_logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from app.marketDataApi.binance import fetch_candles, get_valid_binance_symbols

logger = get_task_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
#  ⌚  Candle lengths in milliseconds — used to align startTime to candle open
# ──────────────────────────────────────────────────────────────────────────────
INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,  # approximated (30 d)
}


class BinanceProvider:
    """Adapter that conforms to IDataProvider, with injected async Mongo and sync Redis clients."""
    name = "Binance"

    # ---------------------------------------------------------------------- init
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

    # ------------------------------------------------------------ public methods
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
        Fetch OHLCV data from Binance, cache in Redis, and persist to Mongo.

        *Rounds* `start` down to the nearest candle open so that the exchange
        actually returns data instead of an empty array when `start` falls
        **inside** a candle.
        """
        loop = get_running_loop()

        # ────────── 1) HTTP fetch in a thread pool
        def _hit_http(s: str, ivl: str, lim: int, dt: datetime | None) -> pd.DataFrame:
            start_ms: Optional[int] = None
            if dt is not None:
                ms  = int(dt.timestamp() * 1000)
                ms -= ms % INTERVAL_MS[ivl]           # ← align to candle open
                start_ms = ms

            return self._fetch(s, ivl, lim, start_ms)

        df: pd.DataFrame = await loop.run_in_executor(None, _hit_http, symbol, interval, limit, start)

        # One safety retry: if the aligned request still returns nothing,
        # try once without startTime (Binance gives the last `limit` candles).
        if df.empty:
            df = await loop.run_in_executor(None, self._fetch, symbol, interval, limit, None)

        if df.empty:
            logger.warning("%s@%s: Binance returned no candles", symbol, interval)
            return df

        logger.info("%s@%s: fetched %d candles", symbol, interval, len(df))

        # ────────── 2) Cache raw dataframe in Redis (sync client)
        try:
            cache_key = f"{symbol}:{interval}:{start.isoformat() if start else 'none'}:{limit}"
            # note: redis-py (sync) → run in executor
            await loop.run_in_executor(
                None,
                lambda: self._redis.set(cache_key, df.to_json(), ex=3600)
            )
        except Exception as exc:
            logger.debug("Redis cache failed for %s: %s", cache_key, exc)

        # ────────── 3) Upsert to MongoDB (async)
        try:
            coll = self._mongo["candles"]
            # bulk writes are faster, but single upserts are simpler / idempotent
            ops = []
            for row in df.to_dict(orient="records"):
                ops.append(
                    (
                        {"symbol": symbol, "interval": interval, "open_time": row["open_time"]},
                        {"$set": row},
                    )
                )
            for flt, upd in ops:
                await coll.update_one(flt, upd, upsert=True)

            logger.info("%s@%s: persisted %d candles to Mongo", symbol, interval, len(ops))
        except Exception:
            logger.exception("Failed to persist %s@%s to MongoDB", symbol, interval)

        return df
