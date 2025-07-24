from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# ─────────────────────────────────────────────────────────────
# 1️⃣  Pick the dotenv file based on PROFILE (dev / prod / staging …)
#    The file is optional; env vars always override.
# ─────────────────────────────────────────────────────────────
PROFILE = os.getenv("PROFILE", "development")
DOTENV_FILE = f".env.{PROFILE}" if Path(f".env.{PROFILE}").exists() else ".env"
load_dotenv(dotenv_path=DOTENV_FILE, override=False)

# ─────────────────────────────────────────────────────────────
# 2️⃣  Settings
# ─────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    """Single source of truth for configuration."""

    # Execution layer: API server vs sandbox container
    KWONTBOT_MODE: Literal["main", "sandbox"] = Field(
        "main", env="KWONTBOT_MODE"
    )

    # Deployment profile: dev, prod, staging – read‑only
    PROFILE: str = PROFILE  # exported for convenience

    # MongoDB
    MONGO_URI_MASTER: str = Field(
        "mongodb://localhost:27017",
        env=["MONGO_URI_MASTER", "MONGO_URI"]
    )
    MONGO_URI_SLAVE: Optional[str] = Field(None, env="MONGO_URI_SLAVE")
    MONGO_DB: str = Field("trading", env="MONGO_DB")

    # in Settings(...)
    MONGO_AUTH_ENABLED: bool = Field(False, env="MONGO_AUTH_ENABLED")

    # Redis / Celery
    REDIS_BROKER_URL: str = Field("redis://localhost:6379/0", env="REDIS_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")

    # Postgres (if used elsewhere)
    POSTGRES_DSN: Optional[str] = Field(None, env="POSTGRES_DSN")

    # —‑‑‑ Exchange & Data provider keys ‑‑‑—
    BINANCE_API_KEY: Optional[str] = Field(None, env="BINANCE_API_KEY")
    BINANCE_API_SECRET: Optional[str] = Field(None, env="BINANCE_API_SECRET")
    COINMARKETCAP_API_KEY: Optional[str] = Field(None, env="COINMARKETCAP_API_KEY")

    # —‑‑‑ External End‑points (override in env when required) ‑‑‑—
    BINANCE_BASE_URL: str = Field("https://api.binance.com", env="BINANCE_BASE_URL")
    CMC_BASE_URL: str = Field("https://pro-api.coinmarketcap.com", env="CMC_BASE_URL")
    CMC_PAGE_SIZE: int = Field(5000, env="CMC_PAGE_SIZE")

    # —‑‑‑ Security related stuff. to be changed later ‑‑‑—
    SECRET_KEY: str = Field("change-me", env="SECRET_KEY")
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    MAX_REQUEST_SIZE: int = Field(5_000_000, env="MAX_REQUEST_SIZE")
    ALLOWED_ORIGINS: list[str] = Field([], env="ALLOWED_ORIGINS")
    API_KEY: Optional[str] = Field(None, env="API_KEY")

    class Config:
        env_file = DOTENV_FILE
        case_sensitive = False

    # Helper: choose URI according to mode
    @property
    def mongo_uri(self) -> str:
        if self.KWONTBOT_MODE == "sandbox" and self.MONGO_URI_SLAVE:
            return self.MONGO_URI_SLAVE
        return self.MONGO_URI_MASTER

    @property
    def mongo_master_uri(self) -> str:
        return self.MONGO_URI_MASTER

    @property
    def mongo_slave_uri(self) -> str | None:
        return self.MONGO_URI_SLAVE or None

# Accessor for DI / caching
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
