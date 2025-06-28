import logging
from typing import Optional
import pandas as pd

from app.marketDataApi.apiconfig.config import BASE_URL
from app.marketDataApi.utils import retry_request
from app.core.db import mongo_sync_db       # MongoClient for persistence:contentReference[oaicite:11]{index=11}
from app.pydanticConfig.settings import settings
from redis import Redis

# In-memory cache (simple LRU could be added)
_candle_cache = {}

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
    """
    Fetch OHLCV candles for the given symbol/interval.
    First checks in-memory and Redis cache, then MongoDB, then Binance API.
    """
    cache_key = f"{symbol}:{interval}:{start_time}:{limit}"
    # 1) Check in-memory cache ( debug fallback )
    # if cache_key in _candle_cache:
    #     logging.debug(f"Cache HIT (memory) for {cache_key}")
    #     return _candle_cache[cache_key].copy()

    # 2) Check Redis cache
    try:
        redis_client = Redis.from_url(settings.REDIS_BROKER_URL)
        raw_json = redis_client.get(cache_key)
        if raw_json:
            logging.info(f"Cache HIT (Redis) for {cache_key}")
            df = pd.read_json(raw_json)
            _candle_cache[cache_key] = df
            return df.copy()
    except Exception as e:
        logging.warning(f"Redis fetch failed for {cache_key}: {e}")
        redis_client = None  # skip Redis caching if error

    # 3) Check MongoDB for stored candles
    if mongo_sync_db is not None:
        coll = mongo_sync_db["candles"]  # new collection for OHLCV data
        query = {"symbol": symbol, "interval": interval}
        if start_time is not None:
            query["open_time"] = {"$gte": start_time}
        # Fetch up to 'limit' candles
        # If no start_time, get most recent by sorting desc
        if start_time is None:
            docs = list(coll.find(query).sort("open_time", -1).limit(limit))
            docs.reverse()  # ascending by time
        else:
            docs = list(coll.find(query).sort("open_time", 1).limit(limit))
        if docs and len(docs) >= limit:
            df = pd.DataFrame(docs)
            df = df.sort_values("open_time").reset_index(drop=True)
            logging.info(f"Cache HIT (MongoDB) for {symbol} {interval} from {len(docs)} docs")
            # Update caches
            if redis_client:
                try: redis_client.set(cache_key, df.to_json(), ex=3600)
                except: pass
            _candle_cache[cache_key] = df
            return df

    # 4) Fallback: fetch from Binance API
    endpoint = f"{BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": int(limit)}
    if start_time is not None:
        params["startTime"] = int(start_time)
    resp = retry_request(endpoint, method="GET", params=params, timeout=20, max_retries=5)
    if resp is None:
        logging.error(f"API fetch failed for {symbol} {interval}")
        return pd.DataFrame()  # no data

    try:
        raw = resp.json()
    except Exception as e:
        logging.error(f"JSON parse error for {symbol} {interval}: {e}")
        return pd.DataFrame()
    if not raw:
        return pd.DataFrame()

    # Build DataFrame as before
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_asset_volume","num_trades",
        "taker_buy_base","taker_buy_quote","ignored"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("open_time").reset_index(drop=True)

    # Store fetched candles into MongoDB (upsert each candle)
    if mongo_sync_db is not None:
        coll = mongo_sync_db["candles"]
        for _, row in df.iterrows():
            doc = {
                "symbol": symbol,
                "interval": interval,
                "open_time": int(row["open_time"]),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"])
            }
            try:
                coll.update_one(
                    {"symbol": symbol, "interval": interval, "open_time": doc["open_time"]},
                    {"$set": doc},
                    upsert=True
                )
            except Exception as e:
                logging.warning(f"MongoDB upsert failed for {symbol} {interval}: {e}")
    # Cache the result in Redis and memory
    if redis_client is not None:
        try: redis_client.set(cache_key, df.to_json(), ex=3600)
        except: pass
    _candle_cache[cache_key] = df

    return df

