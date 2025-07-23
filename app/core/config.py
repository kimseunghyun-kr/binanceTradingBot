"""
Application Configuration
──────────────────────────────────────────────────────────────────────────
Enhanced configuration with all new features.
"""

import os
from typing import List, Optional
from pathlib import Path

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Base configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    API_V2_STR: str = "/api/v2"
    PROJECT_NAME: str = "TradingBot API"
    VERSION: str = "2.0.0"
    
    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    API_KEY: str = Field(..., env="API_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = Field(
        ["http://localhost:3000", "http://localhost:8000"],
        env="ALLOWED_ORIGINS"
    )
    ALLOWED_HOSTS: List[str] = Field(["*"], env="ALLOWED_HOSTS")
    
    # Rate Limiting
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_BACKTEST: str = "10/minute"
    RATE_LIMIT_GRAPHQL: str = "200/minute"
    
    # IP Filtering
    IP_WHITELIST: Optional[List[str]] = Field(None, env="IP_WHITELIST")
    IP_BLACKLIST: Optional[List[str]] = Field(None, env="IP_BLACKLIST")
    
    # Request Limits
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # MongoDB
    MONGO_URI: str = Field(..., env="MONGO_URI")
    MONGO_DB: str = Field("trading", env="MONGO_DB")
    MONGO_AUTH_ENABLED: bool = Field(False, env="MONGO_AUTH_ENABLED")
    MONGO_READONLY_PASSWORD: Optional[str] = Field(None, env="MONGO_READONLY_PASSWORD")
    
    # Redis
    REDIS_BROKER_URL: str = Field(..., env="REDIS_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(..., env="CELERY_RESULT_BACKEND")
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # PostgreSQL (optional)
    POSTGRES_DSN: Optional[str] = Field(None, env="POSTGRES_DSN")
    
    # External APIs
    BINANCE_API_KEY: Optional[str] = Field(None, env="BINANCE_API_KEY")
    BINANCE_API_SECRET: Optional[str] = Field(None, env="BINANCE_API_SECRET")
    COINMARKETCAP_API_KEY: Optional[str] = Field(None, env="COINMARKETCAP_API_KEY")
    
    # Orchestrator Configuration
    ORCHESTRATOR_POOL_SIZE: int = Field(5, env="ORCHESTRATOR_POOL_SIZE")
    ORCHESTRATOR_MAX_RUNS: int = Field(50, env="ORCHESTRATOR_MAX_RUNS")
    ORCHESTRATOR_CONTAINER_TTL: int = Field(3600, env="ORCHESTRATOR_CONTAINER_TTL")
    ORCHESTRATOR_IMAGE: str = Field("tradingbot_orchestrator:concurrent", env="ORCHESTRATOR_IMAGE")
    
    # Backtest Configuration
    BACKTEST_MAX_SYMBOLS: int = Field(50, env="BACKTEST_MAX_SYMBOLS")
    BACKTEST_MAX_ITERATIONS: int = Field(10000, env="BACKTEST_MAX_ITERATIONS")
    BACKTEST_DEFAULT_CAPITAL: float = Field(10000.0, env="BACKTEST_DEFAULT_CAPITAL")
    
    # Celery Configuration
    CELERY_TASK_TIME_LIMIT: int = Field(3600, env="CELERY_TASK_TIME_LIMIT")
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(3300, env="CELERY_TASK_SOFT_TIME_LIMIT")
    CELERY_MAX_RETRIES: int = Field(3, env="CELERY_MAX_RETRIES")
    
    # Logging
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = Field(None, env="LOG_FILE")
    
    # GraphQL
    GRAPHQL_MAX_DEPTH: int = Field(10, env="GRAPHQL_MAX_DEPTH")
    GRAPHQL_MAX_COMPLEXITY: int = Field(1000, env="GRAPHQL_MAX_COMPLEXITY")
    
    # Monitoring
    ENABLE_METRICS: bool = Field(True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(9090, env="METRICS_PORT")
    
    # Docker
    DOCKER_NETWORK: str = Field("tradingbot_network", env="DOCKER_NETWORK")
    DOCKER_REGISTRY: Optional[str] = Field(None, env="DOCKER_REGISTRY")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Allow extra fields for forward compatibility
        extra = "allow"
    
    def get_mongo_settings(self, read_only: bool = False) -> dict:
        """Get MongoDB connection settings."""
        if read_only and self.MONGO_AUTH_ENABLED:
            # Return read-only connection settings
            return {
                "uri": self.MONGO_URI.replace(
                    "://", "://backtest_readonly:" + (self.MONGO_READONLY_PASSWORD or "readonly") + "@"
                ),
                "db": self.MONGO_DB,
                "read_preference": "secondaryPreferred"
            }
        return {
            "uri": self.MONGO_URI,
            "db": self.MONGO_DB
        }
    
    def get_redis_settings(self) -> dict:
        """Get Redis connection settings."""
        return {
            "broker_url": self.REDIS_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "cache_ttl": self.REDIS_CACHE_TTL
        }
    
    def get_security_settings(self) -> dict:
        """Get security-related settings."""
        return {
            "secret_key": self.SECRET_KEY,
            "api_key": self.API_KEY,
            "allowed_origins": self.ALLOWED_ORIGINS,
            "allowed_hosts": self.ALLOWED_HOSTS,
            "rate_limits": {
                "default": self.RATE_LIMIT_DEFAULT,
                "backtest": self.RATE_LIMIT_BACKTEST,
                "graphql": self.RATE_LIMIT_GRAPHQL
            }
        }
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.ENVIRONMENT.lower() == "testing"


# Create global settings instance
settings = Settings()