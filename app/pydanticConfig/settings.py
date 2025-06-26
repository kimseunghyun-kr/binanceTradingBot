from pydantic import BaseSettings


class Settings(BaseSettings):
    """Load configuration from environment variables (.env file)."""
    # API Keys
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    COINMARKETCAP_API_KEY: str

    # Database connections
    MONGO_URI: str = "mongodb://mongo:27017/trading"
    MONGO_DATABASE: str = "trading"
    POSTGRES_DSN: str = ""  # e.g. "postgresql://user:pass@host:port/dbname"

    # Celery broker/backend
    REDIS_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"  # automatically load from .env
        case_sensitive = False


# Instantiate settings object for global use
settings = Settings()
