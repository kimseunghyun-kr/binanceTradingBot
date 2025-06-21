import logging
from typing import List

from marketDataApi.apiconfig.config import CMC_BASE_URL, CMC_PAGE_SIZE, CMC_API_KEY
from marketDataApi.utils import retry_request


###############################################################################
# FETCH MULTIPLE PAGES FROM COINMARKETCAP
###############################################################################
def fetch_coinmarketcap_coins_multi_pages(
        min_cap: float = 200_000_000,
        max_cap: float = 20_000_000_000,
        max_pages: int = 4
) -> List[dict]:
    all_coins = []
    logging.info(f"Fetching up to {max_pages} pages from CoinMarketCap, sir...")

    for page_index in range(max_pages):
        start_val = page_index * CMC_PAGE_SIZE + 1
        logging.info(f"Fetching page {page_index + 1}, start={start_val}...")
        url = f"{CMC_BASE_URL}/v1/cryptocurrency/listings/latest"
        params = {
            "start": str(start_val),
            "limit": str(CMC_PAGE_SIZE),
            "convert": "USD"
        }
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": CMC_API_KEY
        }

        resp = retry_request(url, method="GET", params=params, headers=headers, timeout=30)
        if resp is None:
            logging.warning(f"Could not get page {page_index + 1}, stopping.")
            break

        data = resp.json()
        page_coins = data.get("marketDataApi", [])
        if not page_coins:
            logging.info("Empty marketDataApi returned — no more coins, sir.")
            break
        all_coins.extend(page_coins)

        if len(page_coins) < CMC_PAGE_SIZE:
            logging.info("Reached last partial page, sir.")
            break

    matched = []
    for coin in all_coins:
        try:
            cap = coin["quote"]["USD"]["market_cap"]
        except KeyError:
            continue
        if cap is not None and min_cap <= cap <= max_cap:
            matched.append(coin)

    logging.info(f"Total coins fetched: {len(all_coins)}. Filtered down to: {len(matched)}.")
    return matched