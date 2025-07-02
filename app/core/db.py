import logging

from databases import Database
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from redis import Redis

from app.pydanticConfig.settings import settings

# Async Mongo client
mongo_client: AsyncIOMotorClient = None
mongo_db = None

# Sync Mongo client
mongo_sync_client: MongoClient = None
mongo_sync_db = None

# Init MongoDB (Async + Sync)
if settings.MONGO_URI:
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    mongo_sync_client = MongoClient(settings.MONGO_URI)

    # Choose DB name
    db_name = settings.MONGO_DATABASE or mongo_client.get_default_database().name

    # Select DB (Async)
    mongo_db = mongo_client[db_name]

    # Select DB (Sync)
    mongo_sync_db = mongo_sync_client[db_name]
    logging.info(f"[Mongo] Connected (async & sync) using DB: {db_name}")
    mongo_sync_db["candles"].create_index(
        [("symbol", 1), ("interval", 1), ("open_time", 1)], unique=True
    )

# PostgreSQL
database: Database = None
if settings.POSTGRES_DSN:
    database = Database(settings.POSTGRES_DSN)
    logging.info(f"[Postgres] Configured: {settings.POSTGRES_DSN}")

# Redis
redis_cache: Redis = None
if settings.REDIS_BROKER_URL:
    try:
        redis_cache = Redis.from_url(settings.REDIS_BROKER_URL, decode_responses=True)
    except Exception as e:
        logging.error(f"Redis connection failed: {e}")
        redis_cache = None
print(redis_cache)
