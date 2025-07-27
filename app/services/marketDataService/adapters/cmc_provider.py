# app/services/marketDataService/adapters/cmc_provider.py

from __future__ import annotations

from asyncio import get_running_loop
from typing import Callable, List, Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from app.marketDataApi.coinmarketcap import fetch_coinmarketcap_coins_multi_pages


class CMCProvider:
    """Adapter that conforms to IDataProvider for CMC metadata, with optional caching/persistence."""
    name = "CMC"

    def __init__(
        self,
        redis_client: Redis,
        mongo_async: AsyncIOMotorDatabase,
        fetch_fn: Callable[[], List[dict[str, Any]]] = fetch_coinmarketcap_coins_multi_pages,
    ):
        self._redis = redis_client
        self._mongo = mongo_async
        self._fetch_fn = fetch_fn

    async def list_symbols(self) -> List[str]:
        """Retrieve coin list, convert to USDT pairs, and optionally cache."""
        loop = get_running_loop()
        coins = await loop.run_in_executor(None, self._fetch_fn)
        symbols = [c.get("symbol", "") + "USDT" for c in coins]

        # optional Redis caching
        try:
            # store as JSON string
            import json
            await self._redis.set("cmc:symbols", json.dumps(symbols), ex=3600)
        except Exception:
            pass

        return symbols

    async def fetch_ohlcv(self, *args, **kwargs) -> None:
        """CMC does not support OHLCV data."""
        raise NotImplementedError("CMC only supplies metadata")

    async def fetch_funding(self, *args, **kwargs) -> None:
        """CMC does not support funding data."""
        raise NotImplementedError()
