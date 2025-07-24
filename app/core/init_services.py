# app/core/init_services.py
import logging
from typing import cast

from databases import Database
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from redis import Redis

from app.core.pydanticConfig.settings import get_settings
from app.services.marketDataService.DataServices import DataService
from app.services.marketDataService.adapters.binance_provider import BinanceProvider
from app.services.marketDataService.adapters.cmc_provider import CMCProvider

# ───── Mongo -----------------------------------------------------------
mongo_async: AsyncIOMotorClient | None = None
mongo_sync:  MongoClient | None = None
mongo_db_async = mongo_db_sync = None
data_service = DataService([BinanceProvider(), CMCProvider()])

cfg = get_settings()
if cfg.mongo_uri:
    mongo_async = AsyncIOMotorClient(cfg.mongo_uri)
    mongo_sync  = MongoClient(cfg.mongo_uri)

    mongo_db_async = mongo_async[cfg.MONGO_DB]
    mongo_db_sync  = mongo_sync[cfg.MONGO_DB]

    mongo_db_sync["candles"].create_index(
        [("symbol", 1), ("interval", 1), ("open_time", 1)], unique=True
    )
    logging.info("[Mongo] connected")

# ───── Postgres --------------------------------------------------------
database: Database | None = None
if cfg.POSTGRES_DSN:
    database = Database(cfg.POSTGRES_DSN)
    logging.info("[Postgres] configured")

# ───── Redis -----------------------------------------------------------
redis_cache: Redis | None = None
try:
    redis_cache = Redis.from_url(cfg.REDIS_BROKER_URL, decode_responses=True)
    logging.info("[Redis] connected")
except Exception as e:
    logging.error(f"Redis error: {e}")


def get_mongo_client() -> AsyncIOMotorClient:
    """
    Return the global **ASYNC** Mongo client.

    Raises if the client is still None (e.g. settings missing or
    init_services not imported at application start-up).
    """
    if mongo_async is None:
        raise RuntimeError("Mongo async client not initialised")
    return cast(AsyncIOMotorClient, mongo_async)


def get_mongo_sync() -> MongoClient:
    """Return the global **SYNC** Mongo client."""
    if mongo_sync is None:
        raise RuntimeError("Mongo sync client not initialised")
    return cast(MongoClient, mongo_sync)
