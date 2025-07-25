"""
Initialise Redis, Postgres, external data-feeds.
Mongo pools come from MongoDBConfig (single source of truth).
"""

from __future__ import annotations

import logging
from typing import Optional

from databases import Database
from redis import Redis

from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.services.marketDataService.DataServices import DataService
from app.services.marketDataService.adapters.binance_provider import BinanceProvider
from app.services.marketDataService.adapters.cmc_provider import CMCProvider

log = logging.getLogger(__name__)
cfg = get_settings()
MongoDBConfig.initialize()

# ─── global singletons --------------------------------------------------
postgres_db: Optional[Database] = None
redis_cache: Optional[Redis] = None
data_service = DataService([BinanceProvider(), CMCProvider()])

# ─── bootstrap ----------------------------------------------------------
def _init_external_services() -> None:
    global postgres_db, redis_cache

    # Postgres -----------------------------------------------------------
    if cfg.POSTGRES_DSN:
        postgres_db = Database(cfg.POSTGRES_DSN)
        log.info("[Postgres] configured")

    # Redis --------------------------------------------------------------
    try:
        redis_cache = Redis.from_url(cfg.REDIS_BROKER_URL, decode_responses=True)
        redis_cache.ping()
        log.info("[Redis] connected")
    except Exception as exc:  # pragma: no cover
        log.error("Redis connection error: %s", exc)
        redis_cache = None


_init_external_services()

# ─── public helpers -----------------------------------------------------
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.database import Database as SyncDatabase


def master_db_async() -> AsyncIOMotorDatabase:
    """Primary DB handle (async, read-write)."""
    return MongoDBConfig.master_async()[cfg.db_app]


def slave_db_sync() -> SyncDatabase:
    """Secondary-preferred DB handle (sync, read-only)."""
    return MongoDBConfig.slave_sync()[cfg.db_app]


def get_postgres_db() -> Database:
    if postgres_db is None:
        raise RuntimeError("PostgreSQL not configured")
    return postgres_db


def get_redis_cache() -> Redis:
    if redis_cache is None:
        raise RuntimeError("Redis not configured")
    return redis_cache


def get_data_service() -> DataService:
    return data_service


# --- legacy shims (soft deprecation) -----------------------------------
def get_mongo_client():
    """Deprecated.  Use master_db_async() / slave_db_sync()."""
    return MongoDBConfig.master_async()


def get_mongo_sync():
    """Deprecated.  Use master_db_async() / slave_db_sync()."""
    return MongoDBConfig.master_sync()
