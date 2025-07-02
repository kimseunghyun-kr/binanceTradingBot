# orchestrator_repo.py

from typing import Optional

import pandas as pd
from pymongo import MongoClient


class CandleRepository:
    def __init__(self, mongo_uri, db_name):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.candles = self.db["candles"]

    def fetch_candles(self, symbol: str, interval: str, limit: int = 100,
                      start_time: Optional[int] = None) -> pd.DataFrame:
        query = {"symbol": symbol, "interval": interval}
        if start_time is not None:
            query["open_time"] = {"$gte": start_time}
        # Fetch up to 'limit' candles
        if start_time is None:
            docs = list(self.candles.find(query).sort("open_time", -1).limit(limit))
            docs.reverse()
        else:
            docs = list(self.candles.find(query).sort("open_time", 1).limit(limit))
        if not docs:
            return pd.DataFrame()
        df = pd.DataFrame(docs)
        df = df.sort_values("open_time").reset_index(drop=True)
        return df
