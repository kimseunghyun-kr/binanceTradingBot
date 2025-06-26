import logging
from typing import List

import requests

from app.pydanticConfig.settings import settings

BINANCE_BASE_URL = "https://api.binance.com"
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
CMC_PAGE_SIZE = 5000


class SymbolService:
    @staticmethod
    def get_binance_trading_symbols() -> List[str]:
        endpoint = f"{BINANCE_BASE_URL}/api/v3/exchangeInfo"
        resp = requests.get(endpoint, timeout=10)
        data = resp.json()
        symbols_data = data.get("symbols", [])
        valid_symbols = [s["symbol"] for s in symbols_data
                         if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"]
        return sorted(valid_symbols)

    @staticmethod
    def filter_symbols_by_market_cap(min_cap: float, max_cap: float, max_pages: int, api_key: str) -> List[str]:
        # Ensure API key is available
        api_key = api_key or settings.COINMARKETCAP_API_KEY
        if not api_key:
            # No API key provided; cannot fetch data
            logging.error("CoinMarketCap API key is missing.")
            return []

        all_coins = []
        headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": api_key}
        for page_index in range(max_pages):
            start = page_index * CMC_PAGE_SIZE + 1
            params = {"start": str(start), "limit": str(CMC_PAGE_SIZE), "convert": "USD"}
            resp = requests.get(f"{CMC_BASE_URL}/v1/cryptocurrency/listings/latest", params=params, headers=headers,
                                timeout=30)
            data = resp.json()
            page_coins = data.get("data", [])
            if not page_coins:
                break
            all_coins.extend(page_coins)
            if len(page_coins) < CMC_PAGE_SIZE:
                break
        filtered_coins = []
        for coin in all_coins:
            try:
                cap = coin["quote"]["USD"]["market_cap"]
            except KeyError:
                continue
            if cap is not None and min_cap <= cap <= max_cap:
                symbol = coin.get("symbol", "")
                if symbol:
                    filtered_coins.append(symbol.upper() + "USDT")
        binance_symbols = set(SymbolService.get_binance_trading_symbols())
        final_symbols = [sym for sym in filtered_coins if sym in binance_symbols]
        return final_symbols
