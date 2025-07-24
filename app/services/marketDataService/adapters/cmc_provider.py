# app/adapters/cmc_provider.py
from __future__ import annotations

from app.marketDataApi.coinmarketcap import fetch_coinmarketcap_coins_multi_pages

class CMCProvider:
    name = "CMC"

    async def list_symbols(self) -> list[str]:
        coins = fetch_coinmarketcap_coins_multi_pages()
        return [c["symbol"] + "USDT" for c in coins]  # convert to Binance symbol form

    async def fetch_ohlcv(self, *a, **kw):
        raise NotImplementedError("CMC only supplies metadata")

    async def fetch_funding(self, *a, **kw):
        raise NotImplementedError()