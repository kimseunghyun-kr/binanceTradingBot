"""
FundingProvider backed by Mongo.  Documents are expected like:
{ "symbol":"BTCUSDT", "ts": 1718908800, "rate": 0.00025 }
"""
from typing import Protocol

from pymongo import MongoClient

from strategyOrchestrator.Pydantic_config import settings


class FundingProvider(Protocol):
    def get_rate(self, symbol: str, ts: int) -> float: ...


class MongoFundingProvider:
    def __init__(self):
        cli = MongoClient(settings.MONGO_URI)
        self.col = cli[settings.MONGO_DB]["funding_rates"]

    def get_rate(self, symbol: str, ts: int) -> float:
        doc = self.col.find_one({"symbol": symbol, "ts": ts})
        return doc["rate"] if doc else 0.0


# global read-only provider
funding_provider: FundingProvider = MongoFundingProvider()
