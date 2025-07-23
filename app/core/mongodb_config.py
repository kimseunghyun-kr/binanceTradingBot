"""
MongoDB Configuration for Master-Slave Architecture
──────────────────────────────────────────────────────────────────────────
Provides separate read/write connections for different components.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import quote_plus, urlparse, urlunparse

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ReadPreference
from pymongo.errors import ConnectionFailure, OperationFailure

from app.core.pydanticConfig.settings import settings


class MongoDBConfig:
    """
    MongoDB configuration manager for master-slave architecture.

    Architecture:
    - Master (Primary): Full read/write access for FastAPI/Celery
    - Slave (Secondary): Read-only access for Docker containers
    """

    _master_client: Optional[AsyncIOMotorClient] = None
    _slave_client: Optional[MongoClient] = None
    _read_only_uri: Optional[str] = None

    @classmethod
    def initialize(cls):
        """Initialize MongoDB connections with proper permissions."""
        try:
            # Create master connection (async for FastAPI)
            cls._master_client = cls._create_master_client()

            # Create slave connection (sync for orchestrator)
            cls._slave_client = cls._create_slave_client()

            # Setup read-only user if needed
            cls._setup_read_only_user()

            # Generate read-only URI for containers
            cls._read_only_uri = cls._generate_read_only_uri()

            logging.info("MongoDB master-slave architecture initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize MongoDB: {e}")
            raise

    @classmethod
    def _create_master_client(cls) -> AsyncIOMotorClient:
        """Create master client with full read/write access."""
        return AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            maxPoolSize=100,
            minPoolSize=10
        )

    @classmethod
    def _create_slave_client(cls) -> MongoClient:
        """Create slave client with read preference for secondaries."""
        # Parse URI to add read preference
        parsed = urlparse(settings.MONGO_URI)

        # Add read preference to query params
        query_params = parsed.query or ""
        if query_params:
            query_params += "&"
        query_params += "readPreference=secondaryPreferred"

        # Reconstruct URI
        slave_uri = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            query_params,
            parsed.fragment
        ))

        return MongoClient(
            slave_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            maxPoolSize=50,
            minPoolSize=5,
            read_preference=ReadPreference.SECONDARY_PREFERRED
        )

    @classmethod
    def _setup_read_only_user(cls):
        """Create read-only user for Docker containers if not exists."""
        try:
            admin_db = cls._master_client.admin

            # Check if read-only user exists
            users = admin_db.command("usersInfo", "backtest_readonly")

            if not users.get("users"):
                # Create read-only user
                admin_db.command(
                    "createUser",
                    "backtest_readonly",
                    pwd=cls._generate_secure_password(),
                    roles=[
                        {
                            "role": "read",
                            "db": settings.MONGO_DB
                        }
                    ]
                )
                logging.info("Created read-only MongoDB user for containers")

        except OperationFailure as e:
            # User creation might fail if not running with auth or insufficient privileges
            logging.warning(f"Could not create read-only user: {e}")
        except Exception as e:
            logging.error(f"Error setting up read-only user: {e}")

    @classmethod
    def _generate_secure_password(cls) -> str:
        """Generate secure password for read-only user."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))

    @classmethod
    def _generate_read_only_uri(cls) -> str:
        """Generate read-only URI for Docker containers."""
        # Parse existing URI
        parsed = urlparse(settings.MONGO_URI)

        # If auth is enabled, use read-only credentials
        if settings.MONGO_AUTH_ENABLED:
            username = quote_plus("backtest_readonly")
            password = quote_plus(cls._get_read_only_password())
            netloc = f"{username}:{password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
        else:
            netloc = parsed.netloc

        # Add read preference
        query_params = "readPreference=secondaryPreferred&maxStalenessSeconds=90"

        # Reconstruct URI
        read_only_uri = urlunparse((
            parsed.scheme,
            netloc,
            f"/{settings.MONGO_DB}",
            "",
            query_params,
            ""
        ))

        return read_only_uri

    @classmethod
    def _get_read_only_password(cls) -> str:
        """Get read-only password from secure storage."""
        # In production, retrieve from secure key management service
        # For now, use environment variable
        import os
        return os.getenv("MONGO_READONLY_PASSWORD", "readonly_password_123")

    @classmethod
    def get_master_client(cls) -> AsyncIOMotorClient:
        """Get master client for read/write operations."""
        if not cls._master_client:
            cls.initialize()
        return cls._master_client

    @classmethod
    def get_slave_client(cls) -> MongoClient:
        """Get slave client for read-only operations."""
        if not cls._slave_client:
            cls.initialize()
        return cls._slave_client

    @classmethod
    def get_read_only_uri(cls) -> str:
        """Get read-only URI for Docker containers."""
        if not cls._read_only_uri:
            cls.initialize()
        return cls._read_only_uri

    @classmethod
    async def ensure_indexes(cls):
        """Ensure all required indexes exist."""
        db = cls._master_client[settings.MONGO_DB]

        # Symbols collection indexes
        await db.symbols.create_index([("symbol", 1)], unique=True)
        await db.symbols.create_index([("market_cap", -1)])
        await db.symbols.create_index([("volume_24h", -1)])
        await db.symbols.create_index([("tags", 1)])
        await db.symbols.create_index([("sector", 1)])

        # Candles collection indexes
        await db.candles.create_index([
            ("symbol", 1),
            ("interval", 1),
            ("timestamp", -1)
        ], unique=True)

        # Backtest results indexes
        await db.backtest_results.create_index([("metadata.strategy_name", 1)])
        await db.backtest_results.create_index([("created_at", -1)])
        await db.backtest_results.create_index([("total_return", -1)])

        # Strategies collection indexes
        await db.strategies.create_index([("name", 1)], unique=True)
        await db.strategies.create_index([("type", 1)])
        await db.strategies.create_index([("is_active", 1)])

        logging.info("MongoDB indexes created successfully")

    @classmethod
    async def validate_connections(cls) -> Dict[str, bool]:
        """Validate all MongoDB connections."""
        results = {
            "master_write": False,
            "master_read": False,
            "slave_read": False,
            "read_only_uri": False
        }

        try:
            # Test master write
            test_doc = {"_id": "connection_test", "timestamp": datetime.utcnow()}
            await cls._master_client[settings.MONGO_DB].test.replace_one(
                {"_id": "connection_test"},
                test_doc,
                upsert=True
            )
            results["master_write"] = True

            # Test master read
            doc = await cls._master_client[settings.MONGO_DB].test.find_one(
                {"_id": "connection_test"}
            )
            results["master_read"] = doc is not None

            # Test slave read
            doc = cls._slave_client[settings.MONGO_DB].test.find_one(
                {"_id": "connection_test"}
            )
            results["slave_read"] = doc is not None

            # Test read-only URI
            try:
                test_client = MongoClient(cls._read_only_uri, serverSelectionTimeoutMS=5000)
                test_client.server_info()
                results["read_only_uri"] = True
                test_client.close()
            except:
                pass

        except Exception as e:
            logging.error(f"Connection validation failed: {e}")

        return results


# Global instance
mongodb_config = MongoDBConfig()