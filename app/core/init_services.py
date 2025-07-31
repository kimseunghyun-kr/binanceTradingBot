"""
Initialise Redis, Postgres, and expose Mongo DB handles via small factories.

Important:
    • Mongo connection pools live exclusively in MongoDBConfig.
    • Each call to db_factory(...) returns *the same* Database object
      (cached internally), so you can call it anywhere without worrying.
"""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import Literal, Optional, TypedDict

from databases import Database
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.database import Database as SyncDatabase
from redis import Redis

from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.services.marketDataService.DataServices import DataService
from app.services.marketDataService.adapters.binance_provider import BinanceProvider
from app.services.marketDataService.adapters.cmc_provider import CMCProvider
from app.services.orchestrator import Docker_Engine

log = logging.getLogger(__name__)
cfg = get_settings()

# Avoid double-initialisation under uvicorn --reload (the "reloader" process)
if os.getenv("RUN_MAIN") == "true" or os.getenv("RUN_MAIN") is None:
    MongoDBConfig.initialize()   # make sure pools exist

# ─────────────────────────────────────────────────────────────
# Global singletons (Postgres / Redis / external feeds)
# ─────────────────────────────────────────────────────────────
postgres_db: Optional[Database] = None
redis_cache: Optional[Redis] = None

if cfg.POSTGRES_DSN:
    postgres_db = Database(cfg.POSTGRES_DSN)
    log.info("[Postgres] configured")

try:
    redis_cache = Redis.from_url(cfg.REDIS_BROKER_URL, decode_responses=True)
    redis_cache.ping()
    log.info("[Redis] connected")
except Exception as exc:  # pragma: no cover
    # Do not crash at import-time; just disable rate-limit later.
    log.warning("Redis unavailable – rate-limit middleware will be disabled: %s", exc)
    redis_cache = None


# ─────────────────────────────────────────────────────────────
# MongoDB factory helpers
# ─────────────────────────────────────────────────────────────
Role = Literal["master", "slave"]     # PRIMARY vs secondaryPreferred
Flavour = Literal["async", "sync"]    # Motor vs blocking PyMongo
Logical = Literal["app", "ohlcv", "perp"]


class _CacheKey(TypedDict):
    role: Role
    flavour: Flavour
    logical: Logical


@lru_cache(maxsize=None)
def mongo_db(role: Role, flavour: Flavour, logical: Logical) -> SyncDatabase | AsyncIOMotorDatabase:
    """
    Universal factory:

        mongo_db("master", "async", "app")  -> AsyncIOMotorDatabase
        mongo_db("slave",  "sync",  "ohlcv") -> pymongo.database.Database

    The result is cached, so subsequent calls are free.
    """
    # pick pool ----------------------------------------------------------
    if role == "master":
        client = MongoDBConfig.get_master_client() if flavour == "async" else MongoDBConfig.get_master_client_sync()
    else:  # slave
        if flavour == "async":
            # Motor has no concept of secondaryPreferred per-op; reuse master but pass read_pref later
            client = MongoDBConfig.get_master_client()
        else:
            client = MongoDBConfig.get_slave_client()

    # pick DB name -------------------------------------------------------
    LOGICAL_TO_DB: dict[Logical, str] = {
        "app": cfg.db_app,
        "ohlcv": cfg.db_ohlcv or cfg.db_app,
        "perp": cfg.db_perp or cfg.db_app,
    }
    name = LOGICAL_TO_DB[logical]

    db = client[name]  # type: ignore[index]

    # Motor secondary read_pref tweak (only when async+slave)
    if role == "slave" and flavour == "async":
        from pymongo import ReadPreference
        db = db.with_options(read_preference=ReadPreference.SECONDARY_PREFERRED)

    return db


# ─────────────────────────────────────────────────────────────
# Convenience wrappers used most often
# ─────────────────────────────────────────────────────────────
def master_db_app_async() -> AsyncIOMotorDatabase:
    return mongo_db("master", "async", "app")  # type: ignore[return-value]


def _in_async_context() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False  # no loop -> sync context
    else:
        return True  # a loop is running


def master_db_app_sync() -> SyncDatabase:
    # Guard: prevent usage from an async context
    if _in_async_context():
        raise RuntimeError(
            "master_db_app_sync() called inside an async context – "
            "use master_db_app_async() instead."
        )
    return mongo_db("master", "sync", "app")  # type: ignore[return-value]


def slave_db_app_sync() -> SyncDatabase:
    return mongo_db("slave", "sync", "app")    # type: ignore[return-value]

def master_db_ohlcv_async() -> AsyncIOMotorDatabase:
    return mongo_db("master", "async", "ohlcv")  # type: ignore[return-value]


def master_db_ohlcv_sync() -> SyncDatabase:
    return mongo_db("master", "sync", "ohlcv")   # type: ignore[return-value]


def slave_db_ohlcv_sync() -> SyncDatabase:
    return mongo_db("slave", "sync", "ohlcv")    # type: ignore[return-value]

# ─────────────────────────────────────────────────────────────
# Still expose Redis/Postgres/DataService
# ─────────────────────────────────────────────────────────────
def get_postgres_db() -> Database:
    if postgres_db is None:
        raise RuntimeError("PostgreSQL not configured")
    return postgres_db


def get_redis_cache() -> Redis:
    if redis_cache is None:
        raise RuntimeError("Redis not configured")
    return redis_cache


data_service = DataService([
    BinanceProvider(
      redis_client = get_redis_cache(),
      mongo_async   = master_db_app_async(),
    ),
    CMCProvider(
        redis_client = get_redis_cache(),
        mongo_async   = master_db_app_async(),
    ),
])

def get_data_service() -> DataService:
    return data_service

# Initialize Orchestrator Service
Docker_Engine.initialize()

# ─────────────────────────────────────────────────────────────
# Optional pool lifecycle helpers (imported by FastAPI entrypoint)
# ─────────────────────────────────────────────────────────────
async def open_pools() -> None:
    if postgres_db:
        await postgres_db.connect()

def close_pools() -> None:
    MongoDBConfig.close()
    if postgres_db:
        import anyio; anyio.run(postgres_db.disconnect)  # safe in sync shutdown
    if redis_cache:
        redis_cache.close()
