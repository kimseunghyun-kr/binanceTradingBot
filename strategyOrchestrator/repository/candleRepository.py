# orchestrator_repo.py
from datetime import datetime
from typing import Optional

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING


class CandleRepository:
    def __init__(self, mongo_uri: str, db_name: str, read_only: bool = False):
        self._client = MongoClient(mongo_uri, tz_aware=True)
        self._col    = self._client[db_name].candles

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        start_time: Optional[int] = None,
        newest_first: bool = False,
    ) -> pd.DataFrame:
        q = {"symbol": symbol, "interval": interval}
        if start_time:
            q["timestamp"] = {"$lte": datetime.utcfromtimestamp(start_time / 1000)}
        order = DESCENDING if newest_first else ASCENDING
        cur = self._col.find(q, {"_id": 0}).sort("timestamp", order).limit(limit)
        data = list(cur)
        if newest_first:
            data.reverse()
        return pd.DataFrame(data)
