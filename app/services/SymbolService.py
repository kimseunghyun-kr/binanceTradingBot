import requests
import logging
from typing import List

from app.pydanticConfig.settings import settings

# Endpoints and constants for external APIs
BINANCE_BASE_URL = "https://api.binance.com"
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
CMC_PAGE_SIZE = 5000


class SymbolService:
    """Service for fetching and filtering symbols from Binance and CoinMarketCap."""

    @staticmethod
    def get_binance_trading_symbols() -> List[str]:
        """
        Fetch all Binance symbols that trade against USDT and are active.
        """
        endpoint = f"{BINANCE_BASE_URL}/api/v3/exchangeInfo"
        params = {}
        # Try a few times in case of transient network issues
        for attempt in range(5):
            try:
                resp = requests.get(endpoint, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                symbols_data = data.get("symbols", [])
                valid_symbols = [s["symbol"] for s in symbols_data
                                 if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"]
                logging.info(f"Fetched {len(valid_symbols)} Binance trading symbols (USDT pairs).")
                return sorted(valid_symbols)
            except Exception as e:
                logging.error(f"Error fetching Binance symbols (attempt {attempt + 1}/5): {e}")
                if attempt == 4:
                    return []  # on final attempt, give up
        return []

    @staticmethod
    def fetch_coinmarketcap_listings(max_pages: int = 4) -> List[dict]:
        """
        Fetch cryptocurrency listings from CoinMarketCap API (multiple pages).
        Returns the combined list of coin data dictionaries.
        """
        all_coins = []
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": settings.COINMARKETCAP_API_KEY
        }
        for page_index in range(max_pages):
            start = page_index * CMC_PAGE_SIZE + 1
            params = {"start": str(start), "limit": str(CMC_PAGE_SIZE), "convert": "USD"}
            try:
                resp = requests.get(f"{CMC_BASE_URL}/v1/cryptocurrency/listings/latest",
                                    params=params, headers=headers, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                logging.warning(f"Could not get CoinMarketCap page {page_index + 1}: {e}")
                break
            data = resp.json()
            page_coins = data.get("data", [])
            if not page_coins:
                break
            all_coins.extend(page_coins)
            if len(page_coins) < CMC_PAGE_SIZE:
                # Last page (partial)
                break
        logging.info(f"Fetched {len(all_coins)} coin listings from CoinMarketCap.")
        return all_coins

    @staticmethod
    def filter_symbols_by_market_cap(min_cap: float = 150_000_000, max_cap: float = 20_000_000_000,
                                     max_pages: int = 5, symbol_utils=None) -> List[str]:
        """
        Filter symbols based on market capitalization range using CoinMarketCap data:
        - Fetches coin listings from CoinMarketCap (up to max_pages).
        - Filters coins with USD market_cap between min_cap and max_cap.
        - Maps coin symbols to Binance symbols (symbol + 'USDT') and intersects with actual Binance trading symbols.
        - Saves the filtered list to file and updates the global symbol list.
        """
        # 1. Fetch coin data from CMC and filter by market cap range
        coins = SymbolService.fetch_coinmarketcap_listings(max_pages=max_pages)
        filtered_coins = []
        for coin in coins:
            try:
                cap = coin["quote"]["USD"]["market_cap"]
            except KeyError:
                continue
            if cap is not None and min_cap <= cap <= max_cap:
                symbol = coin.get("symbol", "")
                if symbol:
                    filtered_coins.append(symbol.upper() + "USDT")
        if not filtered_coins:
            logging.info("No coins found in the specified market cap range.")
            symbol_utils.save_filtered_symbols_to_file([])  # save empty (or keep old list unchanged)
            return []
        # 2. Fetch valid Binance symbols and intersect with the filtered list
        binance_symbols = set(SymbolService.get_binance_trading_symbols())
        final_symbols = [sym for sym in filtered_coins if sym in binance_symbols]
        # 3. Save to file and update global list
        symbol_utils.save_filtered_symbols_to_file(final_symbols)
        logging.info(f"Filtered symbols by market cap: {final_symbols}")
        return final_symbols
