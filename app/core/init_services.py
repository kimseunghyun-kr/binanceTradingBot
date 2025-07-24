# app/core/init_services.py
"""
Service initialization module - provides global access to database clients and services.
This module is being refactored to use mongodb_config for proper master-slave separation.
"""
import logging
from typing import Optional

from databases import Database
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database as PyMongoDatabase
from redis import Redis

from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.services.marketDataService.DataServices import DataService
from app.services.marketDataService.adapters.binance_provider import BinanceProvider
from app.services.marketDataService.adapters.cmc_provider import CMCProvider

logger = logging.getLogger(__name__)

# ───── Global instances ─────────────────────────────────────────────────
mongodb_config: Optional[MongoDBConfig] = None
postgres_database: Optional[Database] = None
redis_cache: Optional[Redis] = None
data_service: DataService = DataService([BinanceProvider(), CMCProvider()])

# ───── Initialization ───────────────────────────────────────────────────
def initialize_services():
    """
    Initialize all services. Should be called once at application startup.
    Note: MongoDB initialization is now handled by mongodb_config in KwontBot.py
    """
    global postgres_database, redis_cache
    
    cfg = get_settings()
    
    # ───── Postgres ────────────────────────────────────────────────────
    if cfg.POSTGRES_DSN:
        postgres_database = Database(cfg.POSTGRES_DSN)
        logger.info("[Postgres] configured")
    
    # ───── Redis ───────────────────────────────────────────────────────
    try:
        redis_cache = Redis.from_url(cfg.REDIS_BROKER_URL, decode_responses=True)
        redis_cache.ping()  # Test connection
        logger.info("[Redis] connected")
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        redis_cache = None

# ───── MongoDB Access Functions ─────────────────────────────────────────
def set_mongodb_config(config: MongoDBConfig):
    """Set the global MongoDB configuration. Called by KwontBot.py during startup."""
    global mongodb_config
    mongodb_config = config

def get_mongodb_config() -> MongoDBConfig:
    """Get the global MongoDB configuration."""
    if mongodb_config is None:
        raise RuntimeError("MongoDB config not initialized. Ensure KwontBot.py has started properly.")
    return mongodb_config

async def get_master_db_async() -> AsyncIOMotorDatabase:
    """Get async MongoDB master database (for writes)."""
    config = get_mongodb_config()
    return await config.get_master_db_async()

async def get_read_db_async() -> AsyncIOMotorDatabase:
    """Get async MongoDB read-only database (for reads in API layer)."""
    config = get_mongodb_config()
    return await config.get_read_db_async()

def get_master_db_sync() -> PyMongoDatabase:
    """Get sync MongoDB master database (for writes)."""
    config = get_mongodb_config()
    return config.get_master_db_sync()

def get_read_db_sync() -> PyMongoDatabase:
    """Get sync MongoDB read-only database (for reads)."""
    config = get_mongodb_config()
    return config.get_read_db_sync()

# ───── Legacy compatibility functions ───────────────────────────────────
def get_mongo_client() -> AsyncIOMotorClient:
    """
    Legacy: Return the async MongoDB client.
    Deprecated: Use get_master_db_async() or get_read_db_async() instead.
    """
    config = get_mongodb_config()
    return config.master_client_async

def get_mongo_sync() -> MongoClient:
    """
    Legacy: Return the sync MongoDB client.
    Deprecated: Use get_master_db_sync() or get_read_db_sync() instead.
    """
    config = get_mongodb_config()
    return config.master_client_sync

# ───── Other services ───────────────────────────────────────────────────
def get_postgres_db() -> Database:
    """Get PostgreSQL database connection."""
    if postgres_database is None:
        raise RuntimeError("PostgreSQL not configured")
    return postgres_database

def get_redis_cache() -> Redis:
    """Get Redis cache connection."""
    if redis_cache is None:
        raise RuntimeError("Redis not configured or connection failed")
    return redis_cache

def get_data_service() -> DataService:
    """Get the data service instance."""
    return data_service

# Initialize services on module import (except MongoDB which is handled by KwontBot.py)
initialize_services()