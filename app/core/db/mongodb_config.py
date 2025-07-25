"""
Centralised MongoDB connection manager (master / slave, read-only URI).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote_plus, urlparse, urlunparse

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ReadPreference

from app.core.pydanticConfig.settings import get_settings

cfg = get_settings()


class MongoDBConfig:
    """Singleton pool provider."""

    _master_async: Optional[AsyncIOMotorClient] = None
    _master_sync:  Optional[MongoClient]        = None
    _slave_sync:   Optional[MongoClient]        = None
    _ro_uri:       Optional[str]                = None

    # ------------------------------------------------------------------ #
    # bootstrap
    # ------------------------------------------------------------------ #
    @classmethod
    def initialize(cls) -> None:
        if cls._master_async:          # already initialised
            return

        cls._master_async = cls._build_master_async()
        cls._master_sync  = cls._build_master_sync()
        cls._slave_sync   = cls._build_slave_sync()
        cls._setup_ro_user()
        cls._ro_uri       = cls._make_ro_uri()

        logging.info("[MongoDB] pools initialised")

    # ------------------------------------------------------------------ #
    # client builders
    # ------------------------------------------------------------------ #
    @staticmethod
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
    def _build_slave_sync() -> MongoClient:
        """Secondary-preferred sync client (falls back to master URI if needed)."""
        uri = cfg.mongo_slave_uri or cfg.mongo_master_uri
        parsed = urlparse(uri)

        query = parsed.query + "&" if parsed.query else ""
        query += "readPreference=secondaryPreferred"

        slave_uri = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
        )
        return MongoClient(
            slave_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=10_000,
            maxPoolSize=50,
            minPoolSize=5,
            read_preference=ReadPreference.SECONDARY_PREFERRED,
        )

    # ------------------------------------------------------------------ #
    # read-only user + URI
    # ------------------------------------------------------------------ #
    @classmethod
    def _setup_ro_user(cls) -> None:
        """
        Create (once) or reuse the read-only user used by back-test containers.
        Runs synchronously so `initialize()` remains sync.
        """
        admin = cls._master_sync.admin  # sync PyMongo client

        if admin.command("usersInfo", "backtest_readonly")["users"]:
            return  # already exists

        pwd = get_settings().MONGO_USER_PWD
        if not pwd:  # first process ever
            raise ValueError("MONGO_USER_PWD is required")

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
    def _make_ro_uri(cls, * , default_db: str = "admin") -> str:
        uri = cfg.mongo_slave_uri or cfg.mongo_master_uri
        parsed = urlparse(uri)

        if cfg.MONGO_AUTH_ENABLED:
            user = quote_plus("backtest_readonly")
            pw   = quote_plus(cfg.MONGO_USER_PWD)
            netloc = f"{user}:{pw}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
        else:
            netloc = parsed.netloc

            # authSource stays 'admin' because that’s where the user is defined
            query = "authSource=admin&readPreference=secondaryPreferred&maxStalenessSeconds=90"
            return urlunparse((parsed.scheme, netloc, f"/{default_db}", "", query, ""))

    # ------------------------------------------------------------------ #
    # public getters
    # ------------------------------------------------------------------ #
    @classmethod
    def get_master_client(cls) -> AsyncIOMotorClient:
        cls.initialize()
        return cls._master_async

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
        cls.initialize()
        return cls._ro_uri

    # ------------------------------------------------------------------ #
    # extra helpers
    # ------------------------------------------------------------------ #
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create indexes on the primary DBs (idempotent)."""
        db = cls.get_master_client()[cfg.db_app]  # type: ignore[index]

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
        result = dict(master_write=False, master_read=False, slave_read=False, read_only_uri=False)

        try:
            test = {"_id": "conn_test", "ts": datetime.utcnow()}
            await cls._master_async[cfg.db_app].test.replace_one({"_id": "conn_test"}, test, upsert=True)
            result["master_write"] = True
            result["master_read"]  = await cls._master_async[cfg.db_app].test.find_one({"_id": "conn_test"}) is not None

            result["slave_read"] = cls._slave_sync[cfg.db_app].test.find_one({"_id": "conn_test"}) is not None  # type: ignore[index]

            MongoClient(cls._ro_uri, serverSelectionTimeoutMS=5_000).server_info()
            result["read_only_uri"] = True
        except Exception as exc:  # pragma: no cover
            logging.error("[MongoDB] validation error: %s", exc)

        return result

    @classmethod
    def close(cls) -> None:
        """Close all pools (safe to call multiple times)."""
        for cli in (cls._master_async, cls._master_sync, cls._slave_sync):
            try:
                cli.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        cls._master_async = cls._master_sync = cls._slave_sync = None
        logging.info("[MongoDB] pools closed")


# Eagerly initialise for the main process; workers / sandbox can call again
MongoDBConfig.initialize()
