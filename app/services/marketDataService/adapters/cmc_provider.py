# app/services/marketDataService/adapters/cmc_provider.py

from __future__ import annotations
from asyncio import get_running_loop
from typing import Callable, List, Any

from app.marketDataApi.coinmarketcap import fetch_coinmarketcap_coins_multi_pages


class CMCProvider:
    """Adapter that conforms to IDataProvider for CMC metadata."""
    name = "CMC"

    def __init__(
        self,
        fetch_fn: Callable[[], List[dict[str, Any]]] = fetch_coinmarketcap_coins_multi_pages,
    ):
        # Inject the fetching function
        self._fetch_fn = fetch_fn

    async def list_symbols(self) -> List[str]:
        """Retrieve coin list and convert to USDT trading pairs."""
        loop = get_running_loop()
        # Run the potentially blocking HTTP calls in a thread
        coins = await loop.run_in_executor(None, self._fetch_fn)
        return [c.get("symbol", "") + "USDT" for c in coins]

    async def fetch_ohlcv(self, *args, **kwargs) -> None:
        """CMC does not support OHLCV data."""
        raise NotImplementedError("CMC only supplies metadata")

    async def fetch_funding(self, *args, **kwargs) -> None:
        """CMC does not support funding data."""
        raise NotImplementedError()
