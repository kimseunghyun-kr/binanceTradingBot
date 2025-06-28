import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from config_profile import DOTENV_FILE

load_dotenv(DOTENV_FILE)  # Ensure OS env is loaded for code using os.getenv

class Settings(BaseSettings):
    """Load configuration from environment variables (.env file)."""
    # API Keys
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    COINMARKETCAP_API_KEY: str = ""

    # Database connections
    MONGO_URI: str = ""  # No hardcoded default!
    MONGO_DATABASE: str = "trading"
    POSTGRES_DSN: str = ""
    REDIS_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    class Config:
        env_file = DOTENV_FILE
        case_sensitive = False

settings = Settings()
