import logging

import pandas as pd
import requests

from app.pydanticConfig.settings import settings

BINANCE_BASE_URL = "https://api.binance.com"
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
CMC_PAGE_SIZE = 5000


class SymbolService:
    @staticmethod
    def get_binance_trading_symbols_df() -> pd.DataFrame:
        endpoint = f"{BINANCE_BASE_URL}/api/v3/exchangeInfo"
        resp = requests.get(endpoint, timeout=10)
        data = resp.json()
        symbols_data = data.get("symbols", [])
        df = pd.DataFrame(symbols_data)
        # Filter only USDT pairs and TRADING status, add quoteAsset/baseAsset
        df = df[(df["quoteAsset"] == "USDT") & (df["status"] == "TRADING")]
        df = df[["symbol", "baseAsset", "quoteAsset", "status"]]
        return df.reset_index(drop=True)

    @staticmethod
    def get_symbols_by_market_cap(min_cap: float = 0, max_cap: float = 1000000,
                                  max_pages: int = 30, api_key: str = None) -> pd.DataFrame:
        # This is similar to your filter_symbols_by_market_cap, but returns a DataFrame
        api_key = api_key or settings.COINMARKETCAP_API_KEY
        if not api_key:
            logging.error("CoinMarketCap API key is missing.")
            return pd.DataFrame()

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
        records = []
        for coin in all_coins:
            try:
                cap = coin["quote"]["USD"]["market_cap"]
                symbol = coin.get("symbol", "")
                if cap is not None and min_cap <= cap <= max_cap and symbol:
                    records.append({
                        "symbol": symbol.upper() + "USDT",
                        "market_cap": cap
                    })
            except KeyError:
                continue
        df = pd.DataFrame(records)
        # Now filter against actual Binance symbols:
        binance_df = SymbolService.get_binance_trading_symbols_df()
        df = df[df["symbol"].isin(binance_df["symbol"])]
        # Optional: join meta fields
        df = df.merge(binance_df, on="symbol", how="left")
        return df.reset_index(drop=True)
