"""
Centralised MongoDB connection manager (master / slave, read-only URI).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote_plus, urlparse, urlunparse, urlencode, parse_qsl

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ReadPreference
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.pydanticConfig.settings import get_settings

cfg = get_settings()


class MongoDBConfig:
    """
    Pool provider.

    * Sync `MongoClient`s remain **process-wide singletons**.
    * Async `AsyncIOMotorClient`s are now **event-loop scoped**: one per
      `asyncio.run()` loop ⇒ never reused after that loop is closed.
    """

    # process-wide sync pools
    _master_sync: Optional[MongoClient] = None
    _slave_sync:  Optional[MongoClient] = None
    _ro_uri:      Optional[str]         = None

    # per-loop async pools
    _async_clients: ContextVar[Dict[int, AsyncIOMotorClient]] = ContextVar(
        "_async_clients", default={}
    )


    # ------------------------------------------------------------------ #
    # bootstrap
    # ------------------------------------------------------------------ #
    # ───────────────────────── bootstrap (sync only) ───────────────────
    @classmethod
    def initialize(cls) -> None:
        """Build sync pools & RO user; async pools created lazily per loop."""
        if cls._master_sync:  # already initialised in this worker
            return

        cls._master_sync = cls._build_master_sync()
        cls._slave_sync = cls._build_slave_sync()
        cls.lazy_init()  # ping, RO user, etc.
        cls._ro_uri = cls._make_ro_uri()
        logging.info("[MongoDB] sync pools initialised")

        # ─────────────────── per-loop async client helper ──────────────────
    @staticmethod
    def _get_async_client_for_loop() -> AsyncIOMotorClient:
        loop_id = id(asyncio.get_running_loop())
        cache = MongoDBConfig._async_clients.get()
        if loop_id in cache:
            return cache[loop_id]

        client = AsyncIOMotorClient(
            cfg.mongo_master_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=100,
            minPoolSize=10,
        )
        cache[loop_id] = client
        return client

    # ------------------------------------------------------------------ #
    # client builders
    # ------------------------------------------------------------------ #

    @staticmethod
    @retry(stop=stop_after_attempt(6), wait=wait_fixed(2))  # 6×2 s
    def _ping(uri: str):
        MongoClient(uri, serverSelectionTimeoutMS=5000).admin.command("ping")

    @staticmethod
    def lazy_init() -> None:
        MongoDBConfig._ping(os.getenv("MONGO_URI_MASTER"))
        MongoDBConfig._ping(os.getenv("MONGO_URI_SLAVE"))
        MongoDBConfig._setup_ro_user()  # now it’s safe

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _build_master_async() -> AsyncIOMotorClient:
        return AsyncIOMotorClient(
            cfg.mongo_master_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=100,
            minPoolSize=10,
        )


    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _build_master_sync() -> MongoClient:
        return MongoClient(
            cfg.mongo_master_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=5,
            read_preference=ReadPreference.PRIMARY,
        )

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _build_slave_sync() -> MongoClient:
        """Secondary-preferred sync client (falls back to master URI if needed)."""
        uri = cfg.mongo_slave_uri or cfg.mongo_master_uri
        parsed = urlparse(uri)

        # merge query, don't duplicate readPreference
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params.setdefault("readPreference", "secondaryPreferred")

        slave_uri = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, parsed.params,
            urlencode(params, doseq=True), parsed.fragment
        ))

        return MongoClient(
            slave_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=5,
        )

    # ------------------------------------------------------------------ #
    # read-only user + URI
    # ------------------------------------------------------------------ #
    @classmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _setup_ro_user(cls) -> None:
        """
        Create (once) or reuse the read-only user used by back-test containers.
        Runs synchronously so `initialize()` remains sync.
        """
        admin = cls._master_sync.admin  # sync PyMongo client
        logging.info(f"[MongoDB] creating ro user: {admin}")
        if admin.command("usersInfo", "backtest_readonly")["users"]:
            return  # already exists

        pwd = get_settings().MONGO_USER_PW
        if not pwd:  # first process ever
            raise ValueError("MONGO_USER_PW is required")

        admin.command(
            "createUser",
            "backtest_readonly",
            pwd=pwd,
            roles=[{"role": "read", "db": cfg.db_app},
                   {"role": "read", "db": cfg.db_ohlcv},
                   {"role": "read", "db": cfg.db_perp},
                   ],
        )
        logging.info("[MongoDB] created read-only user")

    @classmethod
    def _make_ro_uri(cls, *, default_db: str = "admin") -> str:
        uri_in = cfg.mongo_slave_uri or cfg.mongo_master_uri
        parsed = urlparse(uri_in)

        # build netloc (with or without auth)
        if cfg.MONGO_AUTH_ENABLED:
            user = quote_plus("backtest_readonly")
            pwd = quote_plus(cfg.MONGO_USER_PW)
            host = parsed.hostname or ""
            netloc = f"{user}:{pwd}@{host}"
            if parsed.port:
                netloc += f":{parsed.port}"
        else:
            netloc = parsed.netloc

        # merge query params, preserving replicaSet if present
        q = dict(parse_qsl(parsed.query, keep_blank_values=True))
        # ensure required params
        q.setdefault("replicaSet", "rs0")
        q["readPreference"] = "secondaryPreferred"
        q["maxStalenessSeconds"] = "90"
        if cfg.MONGO_AUTH_ENABLED:
            q["authSource"] = "admin"

        query = urlencode(q, doseq=True)
        return urlunparse((parsed.scheme, netloc, f"/{default_db}", "", query, ""))

    # ------------------------------------------------------------------ #
    # public getters
    # ------------------------------------------------------------------ #
    @classmethod
    def get_master_client(cls) -> AsyncIOMotorClient:
        cls.initialize()
        return cls._get_async_client_for_loop()

    @classmethod
    def get_master_client_sync(cls) -> MongoClient:
        cls.initialize()
        return cls._master_sync

    @classmethod
    def get_slave_client(cls) -> MongoClient:
        cls.initialize()
        return cls._slave_sync

    @classmethod
    def get_read_only_uri(cls) -> str:
        logging.info("[MongoDB] read-only uri %s" , cls._ro_uri)
        cls.initialize()
        return cls._ro_uri

    # ------------------------------------------------------------------ #
    # extra helpers
    # ------------------------------------------------------------------ #
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create indexes on the primary DBs (idempotent)."""
        db = cls.get_master_client()[cfg.db_app]  # type: ignore[index]
        await db.backtest_results.create_index("task_id", unique=True)
        await db.symbols.create_index([("symbol", 1)], unique=True)
        await db.candles.create_index(
            [("symbol", 1), ("interval", 1), ("timestamp", -1)], unique=True
        )
        await db.backtest_results.create_index([("metadata.strategy_name", 1)])
        await db.backtest_results.create_index([("created_at", -1)])
        await db.backtest_results.create_index([("total_return", -1)])
        await db.strategies.create_index([("name", 1)], unique=True)
        await db.strategies.create_index([("type", 1)])
        await db.strategies.create_index([("is_active", 1)])

        logging.info("[MongoDB] indexes ensured")

    @classmethod
    async def validate_connections(cls) -> Dict[str, bool]:
        """Ping master, slave and RO endpoints; return bool map."""
        cls.initialize()
        result = dict(
            master_write = False,
            master_read = False,
            slave_read = False,
            read_only_uri = False,
        )

        try:
            test = {"_id": "conn_test", "ts": datetime.utcnow()}
            db_async = cls.get_master_client()[cfg.db_app]  # async client for *this* loop
            await db_async.test.replace_one({"_id": "conn_test"}, test, upsert=True)
            result["master_write"] = True
            result["master_read"] = (
                await db_async.test.find_one({"_id": "conn_test"}) is not None
            )
            result["slave_read"] = cls._slave_sync[cfg.db_app].test.find_one({"_id": "conn_test"}) is not None  # type: ignore[index]

            MongoClient(cls._ro_uri, serverSelectionTimeoutMS=5_000).server_info()
            result["read_only_uri"] = True
        except Exception as exc:  # pragma: no cover
            logging.error("[MongoDB] validation error: %s", exc)

        return result

    @classmethod
    def close(cls) -> None:
        """Close all pools (safe to call multiple times)."""
        # close loop-scoped async clients
        for cli in cls._async_clients.get().values():
            try:
                cli.close()
            except Exception:
                pass
        cls._async_clients.set({})

        # close process-wide sync clients
        for cli in (cls._master_sync, cls._slave_sync):
            try:
                cli.close()
            except Exception:
                pass
        cls._master_sync = cls._slave_sync = None
        logging.info("[MongoDB] pools closed")

