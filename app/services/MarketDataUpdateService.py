from typing import Optional
import pandas as pd
from app.marketDataApi.binance import fetch_candles  # or whatever your fetcher is

def ensure_candles_up_to_date(symbol: str, interval: str,
                              mongo_db,
                              end_time: Optional[int] = None,
                              min_lookback: int = 100) -> pd.DataFrame:
    """
    Ensures OHLCV data for `symbol`/`interval` is up-to-date in Mongo.
    Optionally, updates until `end_time` (timestamp).
    Returns DataFrame for downstream use.
    """
    coll = mongo_db["candles"]
    q = {"symbol": symbol, "interval": interval}
    cursor = coll.find(q).sort("open_time", -1).limit(1)
    last_doc = next(cursor, None)
    # If no data, fetch min_lookback
    if not last_doc:
        df = fetch_candles(symbol, interval, limit=min_lookback)
        # Assumed: fetch_candles inserts/upserts to DB and returns df
        return df
    last_time = last_doc["open_time"]
    # Optionally, end_time can be provided to extend up to a target time
    need_more = (not end_time) or (last_time < end_time)
    if need_more:
        # You may want to fetch in chunks for large gaps
        fetch_limit = 1000
        cur_time = last_time
        while (not end_time) or (cur_time < end_time):
            df = fetch_candles(symbol, interval, limit=fetch_limit, start_time=cur_time+1)
            if df.empty:
                break
            cur_time = df["open_time"].max()
            if cur_time >= end_time:
                break
    # Return full (or recent) dataframe for downstream
    df = pd.DataFrame(list(coll.find(q).sort("open_time", 1)))
    return df
