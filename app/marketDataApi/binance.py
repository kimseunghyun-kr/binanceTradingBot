import logging
from typing import Optional

import pandas as pd
from redis import Redis

from app.marketDataApi.apiconfig.config import BASE_URL
from app.marketDataApi.utils import retry_request

# In-memory cache (simple LRU could be added)
_candle_cache = {}

def _cache_to_redis(client: Redis, key: str, df: pd.DataFrame) -> None:
    """Helper to store a DataFrame in a Redis cache"""
    try :
        client.set(key, df.to_json(), ex = 3600)
    except Exception as e :
        pass

###############################################################################
# GET VALID BINANCE SYMBOLS
###############################################################################
def get_valid_binance_symbols() -> set:
    endpoint = f"{BASE_URL}/api/v3/exchangeInfo"
    resp = retry_request(endpoint, method="GET", params={}, timeout=20, max_retries=5)
    if resp is None:
        logging.error("Failed to fetch Binance exchange info, sir.")
        return set()
    try:
        data = resp.json()
        symbols_data = data.get("symbols", [])
        valid_symbols = set()
        for s in symbols_data:
            if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                valid_symbols.add(s.get("symbol"))
        return valid_symbols
    except Exception as e:
        logging.error(f"Error parsing exchange info: {e}")
        return set()


###############################################################################
# FETCHING CANDLE DATA FROM BINANCE
###############################################################################
def fetch_candles(
    symbol: str,
    interval: str,
    limit: int = 100,
    start_time: Optional[int] = None
) -> pd.DataFrame:
    """
    Pure HTTP → DataFrame.
    No caching or DB writes here.
    """
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time is not None:
        params["startTime"] = start_time

    resp = retry_request(f"{BASE_URL}/api/v3/klines", "GET", params, timeout=20, max_retries=5)
    if not resp:
        logging.error(f"Binance API failed for {symbol}@{interval}")
        return pd.DataFrame()

    raw = resp.json()
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignored"
    ])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.sort_values("open_time").reset_index(drop=True)