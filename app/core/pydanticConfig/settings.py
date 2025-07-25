from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# ─────────────────────────────────────────────────────────────
# Pick dotenv file based on PROFILE (dev / prod / staging …)
# ─────────────────────────────────────────────────────────────
PROFILE = os.getenv("PROFILE", "development")
DOTENV_FILE = f".env.{PROFILE}" if Path(f".env.{PROFILE}").exists() else ".env"
load_dotenv(DOTENV_FILE, override=False)

# ─────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    """
    Canonical configuration object.

    Environment variables always override the .env file.
    """

    # —--- Runtime layer ---—
    KWONTBOT_MODE: Literal["main", "sandbox"] = Field("main", env="KWONTBOT_MODE")
    PROFILE: str = PROFILE

    # —--- MongoDB URIs ---—
    MONGO_URI_MASTER: str = Field("mongodb://localhost:27017", env="MONGO_URI_MASTER")
    MONGO_URI_SLAVE: Optional[str] = Field(None, env="MONGO_URI_SLAVE")
    MONGO_AUTH_ENABLED: bool = Field(False, env="MONGO_AUTH_ENABLED")

    # —--- Databases (logical split) ---—
    MONGO_DB_APP:   str = Field("trading",    env="MONGO_DB_APP")    # default
    MONGO_DB_OHLCV: Optional[str] = Field(None, env="MONGO_DB_OHLCV")
    MONGO_DB_PERP:  Optional[str] = Field(None, env="MONGO_DB_PERP")

    # —--- Redis / Celery ---—
    REDIS_BROKER_URL: str = Field("redis://localhost:6379/0", env="REDIS_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")

    # —--- Optional Postgres ---—
    POSTGRES_DSN: Optional[str] = Field(None, env="POSTGRES_DSN")

    # —--- External API keys (omitted for brevity) ---—
    BINANCE_API_KEY: Optional[str] = Field(None, env="BINANCE_API_KEY")
    BINANCE_API_SECRET: Optional[str] = Field(None, env="BINANCE_API_SECRET")
    COINMARKETCAP_API_KEY: Optional[str] = Field(None, env="COINMARKETCAP_API_KEY")

    # —--- Misc ---—
    SECRET_KEY: str = Field("change-me", env="SECRET_KEY")
    ALLOWED_ORIGINS: str = Field("*", env="ALLOWED_ORIGINS")
    RATE_LIMIT_PER_MINUTE: int = Field(100, env="RATE_LIMIT_PER_MINUTE")

    class Config:
        env_file = DOTENV_FILE
        case_sensitive = False

    # —--- Convenience helpers ---—
    @property
    def mongo_master_uri(self) -> str:            # primary always exists
        return self.MONGO_URI_MASTER

    @property
    def mongo_slave_uri(self) -> str | None:      # may be unset
        return self.MONGO_URI_SLAVE

    @property
    def mongo_uri(self) -> str:                   # generic helper
        return self.MONGO_URI_SLAVE if self.KWONTBOT_MODE == "sandbox" and self.MONGO_URI_SLAVE else self.MONGO_URI_MASTER

    # Logical database names ------------------------------------------------
    @property
    def db_app(self) -> str:
        return self.MONGO_DB_APP

    @property
    def db_ohlcv(self) -> str:
        return self.MONGO_DB_OHLCV or self.MONGO_DB_APP

    @property
    def db_perp(self) -> str:
        return self.MONGO_DB_PERP or self.MONGO_DB_APP

    # ---- hard-fail if someone accesses removed legacy attrs --------------
    def __getattr__(self, item):
        if item in {"MONGO_DB", "mongo_db"}:
            raise AttributeError(
                "'MONGO_DB' is removed.  Use settings.db_app / db_ohlcv / db_perp."
            )
        if item == "MONGO_URI":
            warnings.warn(
                "MONGO_URI is removed.  Use mongo_master_uri / mongo_slave_uri / mongo_uri.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.mongo_master_uri
        raise AttributeError(item)


@lru_cache(1)
def get_settings() -> Settings:
    return Settings()
