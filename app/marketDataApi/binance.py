import logging
from app.marketDataApi.apiconfig.config import BASE_URL
from app.marketDataApi.utils import retry_request
import pandas as pd
from typing import Optional


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
def fetch_candles(symbol: str, interval: str, limit=100, start_time: Optional[int] = None) -> pd.DataFrame:
    endpoint = f"{BASE_URL}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": int(limit)
    }
    if start_time is not None:
        params["startTime"] = int(start_time)

    resp = retry_request(endpoint, method="GET", params=params, timeout=20, max_retries=5)
    if resp is None:
        logging.error(f"Failed to fetch {interval} klines for {symbol} after retries, sir.")
        return pd.DataFrame()
    try:
        raw = resp.json()
    except Exception as e:
        logging.error(f"JSON parse error for {symbol} {interval}: {e}")
        return pd.DataFrame()
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignored"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_values("open_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
