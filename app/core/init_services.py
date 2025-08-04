# app/core/init_services.py
from __future__ import annotations

import asyncio
import logging
import os
from contextvars import ContextVar
from typing import Dict, Literal, Optional, Tuple

from databases import Database
from motor.motor_asyncio import (
    AsyncIOMotorDatabase,
)  # type: ignore
from pymongo.database import Database as SyncDatabase
from redis import Redis

from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.services.marketDataService.DataServices import DataService
from app.services.marketDataService.adapters.binance_provider import BinanceProvider
from app.services.marketDataService.adapters.cmc_provider import CMCProvider

log = logging.getLogger(__name__)
cfg = get_settings()

# ─────────────────────────────────── pools (Postgres / Redis) ─────────────────
postgres_db: Optional[Database] = Database(cfg.POSTGRES_DSN) if cfg.POSTGRES_DSN else None
redis_cache: Optional[Redis] = None  # created in open_pools()

def get_redis_cache() -> Redis:
    if redis_cache is None:
        raise RuntimeError("Redis not connected (call open_pools() first)")
    return redis_cache

# ───────────────────────────── Mongo helpers – per-loop cache ─────────────────
# key = (loop_id, role, flavour, logical)
_DbKey = Tuple[int, str, str, str]
_db_cache: ContextVar[Dict[_DbKey, SyncDatabase | AsyncIOMotorDatabase]] = ContextVar(
    "_db_cache", default={}
)

def _logical_to_name(logical: str) -> str:
    mapping = {
        "app": cfg.db_app,
        "ohlcv": cfg.db_ohlcv or cfg.db_app,
        "perp": cfg.db_perp or cfg.db_app,
    }
    return mapping[logical]

def mongo_db(
    role: Literal["master", "slave"],
    flavour: Literal["async", "sync"],
    logical: Literal["app", "ohlcv", "perp"],
) -> SyncDatabase | AsyncIOMotorDatabase:
    if flavour == "async":
        # async Motor client → bound to the current loop
        loop_id = id(asyncio.get_running_loop())
    else:
      # sync PyMongo client → no event-loop involvement
      # just key on worker PID so we reuse one client per process
        loop_id = os.getpid()

    key: _DbKey = (loop_id, role, flavour, logical)

    cache = _db_cache.get()
    if key in cache:
        return cache[key]

    # ───────── build new client bound to *this* loop ─────────
    if role == "master":
        client = (
            MongoDBConfig.get_master_client()
            if flavour == "async"
            else MongoDBConfig.get_master_client_sync()
        )
    else:
        client = (
            MongoDBConfig.get_master_client()
            if flavour == "async"
            else MongoDBConfig.get_slave_client()
        )

    db = client[_logical_to_name(logical)]  # type: ignore[index]

    if role == "slave" and flavour == "async":
        from pymongo import ReadPreference
        db = db.with_options(read_preference=ReadPreference.SECONDARY_PREFERRED)

    cache[key] = db
    return db

# convenience wrappers ---------------------------------------------------------
def master_db_app_async() -> AsyncIOMotorDatabase:
    return mongo_db("master", "async", "app")  # type: ignore[return-value]

def master_db_app_sync() -> SyncDatabase:
    if _in_async_context():
        raise RuntimeError("Use master_db_app_async() inside async code")
    return mongo_db("master", "sync", "app")  # type: ignore[return-value]

def slave_db_app_sync() -> SyncDatabase:
    return mongo_db("slave", "sync", "app")  # type: ignore[return-value]

def master_db_ohlcv_async() -> AsyncIOMotorDatabase:
    return mongo_db("master", "async", "ohlcv")  # type: ignore[return-value]

def master_db_ohlcv_sync() -> SyncDatabase:
    return mongo_db("master", "sync", "ohlcv")  # type: ignore[return-value]

def slave_db_ohlcv_sync() -> SyncDatabase:
    return mongo_db("slave", "sync", "ohlcv")  # type: ignore[return-value]

def _in_async_context() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False

# ───────────────────────────── DataService – per-loop cache ───────────────────
_data_service_per_loop: ContextVar[Dict[int, DataService]] = ContextVar(
    "_data_service_per_loop", default={}
)

def _build_data_service() -> DataService:
    mongo_db_async = master_db_app_async()  # already loop-safe
    return DataService(
        [
            BinanceProvider(
                redis_client=get_redis_cache(),
                mongo_async=mongo_db_async,
            ),
            CMCProvider(
                redis_client=get_redis_cache(),
                mongo_async=mongo_db_async,
            ),
        ]
    )

def get_data_service() -> DataService:
    loop_id = id(asyncio.get_running_loop())
    cache = _data_service_per_loop.get()
    if loop_id not in cache:
        cache[loop_id] = _build_data_service()
    return cache[loop_id]

# ───────────────────────────── pool lifecycle hooks ───────────────────────────
async def open_pools() -> None:
    """Call from FastAPI startup or Celery worker_process_init."""
    global redis_cache
    if postgres_db:
        await postgres_db.connect()
    if redis_cache is None:
        redis_cache = Redis.from_url(cfg.REDIS_BROKER_URL, decode_responses=True)
        try:
            redis_cache.ping()
            log.info("[Redis] connected")
        except Exception as exc:  # pragma: no cover
            log.warning("Redis unavailable: %s", exc)
            redis_cache = None

def close_pools() -> None:
    """Call from FastAPI shutdown or Celery worker_shutdown."""
    MongoDBConfig.close()
    if postgres_db:
        import anyio
        anyio.run(postgres_db.disconnect)
    if redis_cache:
        redis_cache.close()
