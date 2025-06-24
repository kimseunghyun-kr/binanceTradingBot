import logging
from typing import List
import sys

from app.marketDataApi.apiconfig.config import load_filtered_symbols_from_file, save_filtered_symbols_to_file
from app.marketDataApi.binance import get_valid_binance_symbols
from app.marketDataApi.coinmarketcap import fetch_coinmarketcap_coins_multi_pages


###############################################################################
# INITIALIZE SYMBOLS
###############################################################################
def initialize_symbols() -> List[str]:
    print("Please choose an option, sir:")
    print("1: Filter by market capitalization using CoinMarketCap (multi-page) and save the result.")
    print("2: Import existing filtered coin list from file.")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        coins = fetch_coinmarketcap_coins_multi_pages(
            min_cap=150_000_000,
            max_cap=20_000_000_000,
            max_pages=5
        )
        if not coins:
            logging.info("No coins found with the specified market cap criteria, sir.")
            return []

        symbols = []
        for coin in coins:
            cmc_symbol = coin.get("symbol", "")
            if cmc_symbol:
                binance_symbol = cmc_symbol.upper() + "USDT"
                symbols.append(binance_symbol)

        valid_binance = get_valid_binance_symbols()
        filtered_symbols = [sym for sym in symbols if sym in valid_binance]

        save_filtered_symbols_to_file(filtered_symbols)
        logging.info(f"Filtered symbols: {filtered_symbols}")
        print("Save completed. Run the program again.")
        sys.exit()

    elif choice == "2":
        symbols = load_filtered_symbols_from_file()
        if symbols:
            logging.info(f"Loaded filtered symbols from file: {symbols}")
            return symbols
        else:
            logging.info("No symbols loaded from file.")
            return []
    else:
        logging.info("Invalid choice, sir. Exiting.")
        return []

def initialize_symbols_from_config(cfg: dict) -> List[str]:
    mode = cfg.get("mode", "filter_cmc")
    if mode == "filter_cmc":
        min_cap = cfg.get("min_cap", 150_000_000)
        max_cap = cfg.get("max_cap", 20_000_000_000)
        max_pages = cfg.get("max_pages", 5)
        coins = fetch_coinmarketcap_coins_multi_pages(
            min_cap=min_cap,
            max_cap=max_cap,
            max_pages=max_pages
        )
        if not coins:
            logging.info("No coins found with the specified market cap criteria, sir.")
            return []
        symbols = []
        for coin in coins:
            cmc_symbol = coin.get("symbol", "")
            if cmc_symbol:
                binance_symbol = cmc_symbol.upper() + "USDT"
                symbols.append(binance_symbol)
        valid_binance = get_valid_binance_symbols()
        filtered_symbols = [sym for sym in symbols if sym in valid_binance]
        save_filtered_symbols_to_file(filtered_symbols)
        logging.info(f"Filtered symbols: {filtered_symbols}")
        return filtered_symbols
    elif mode == "load_file":
        filename = cfg.get("filename", "filtered_coins.txt")
        symbols = load_filtered_symbols_from_file(filename)
        if symbols:
            logging.info(f"Loaded filtered symbols from file: {symbols}")
            return symbols
        else:
            logging.info("No symbols loaded from file.")
            return []
    else:
        logging.info("Invalid symbols mode in config. Exiting.")
        return []
