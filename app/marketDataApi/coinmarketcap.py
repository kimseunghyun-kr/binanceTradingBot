import logging
from typing import List

from app.marketDataApi.apiconfig.config import CMC_BASE_URL, CMC_PAGE_SIZE, CMC_API_KEY
from app.marketDataApi.utils import retry_request


def _fetch_page(start_val: int, idx: int) -> List[dict]:
    """Fetch a single page from CoinMarketCap."""

    logging.info(f"Fetching page {idx + 1}, start={start_val}...")
    url = f"{CMC_BASE_URL}/v1/cryptocurrency/listings/latest"
    params = {
        "start": str(start_val),
        "limit": str(CMC_PAGE_SIZE),
        "convert": "USD",
    }
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
    }

    resp = retry_request(url, method="GET", params=params, headers=headers, timeout=30)
    if resp is None:
        logging.warning(f"Could not get page {idx + 1}, stopping.")
        return []

    data = resp.json()
    return data.get("data", [])

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
        page_coins = _fetch_page(start_val, page_index)
        if not page_coins:
            logging.info("Empty data returned — no more coins, sir.")
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
