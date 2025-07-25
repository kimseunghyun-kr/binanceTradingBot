"""Read-only OHLCV accessor for the back-test sandbox."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
from pymongo import ASCENDING, DESCENDING, MongoClient
from app.core.pydanticConfig.settings import get_settings


class CandleRepository:
    """
    Thin wrapper around the `candles` collection.

    • Always connects to the *slave* node (secondaryPreferred).
    • Accepts either an explicit URI or falls back to Settings.
    • Normalises the frame so every call returns
        - ascending order (oldest → newest)
        - a fast-int `open_time` column (ms since epoch)
    """

    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str | None = None,
    ) -> None:
        cfg = get_settings()
        uri = mongo_uri or cfg.mongo_uri                       # ← slave when sandbox
        db  = db_name or cfg.MONGO_DB

        # Enforce secondaryPreferred even if caller passed a primary URI
        self._client = MongoClient(
            uri,
            read_preference="secondaryPreferred",
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=5,
        )
        self._col = self._client[db].candles

    # ---------------------------------------------------------------------
    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        *,
        start_time: Optional[int] = None,      # millis
        newest_first: bool = False,
    ) -> pd.DataFrame:
        """Return up-to-`limit` candles for *symbol* / *interval*."""
        q = {"symbol": symbol, "interval": interval}
        if start_time:
            q["timestamp"] = {"$lte": datetime.utcfromtimestamp(start_time / 1000)}

        order = DESCENDING if newest_first else ASCENDING
        docs  = (
            self._col.find(q, {"_id": 0})
            .sort("timestamp", order)
            .limit(limit)
        )
        data = list(docs)
        if newest_first:
            data.reverse()

        df = pd.DataFrame(data)
        if not df.empty and "timestamp" in df.columns:
            df["open_time"] = df["timestamp"].astype("int64")        # speed
            df.drop(columns="timestamp", inplace=True)

        return df
