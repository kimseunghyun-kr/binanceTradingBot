# app/main.py

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.pydanticConfig.settings import get_settings
from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import open_pools, close_pools, get_redis_cache
from app.core.security import RateLimitMiddleware
from contextlib import asynccontextmanager


# ─── logging -----------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    FastAPI application factory. Sets up startup/shutdown events,
    middleware, routers, and GraphQL endpoint after opening pools.
    """
    cfg = get_settings()

    # Lifespan context to open/close pools
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("🔧 FastAPI startup: opening pools...")
        await open_pools()

        # Attach clients & settings to app
        app.mongo_async = MongoDBConfig.get_master_client()
        app.mongo_sync = MongoDBConfig.get_master_client_sync()
        app.mongo_ro_uri = MongoDBConfig.get_read_only_uri()
        app.redis = get_redis_cache()
        app.settings = cfg

        yield

        close_pools()
        log.info("FastAPI shutdown: pools closed.")

    app = FastAPI(
        title="Trading Bot API",
        description="FastAPI service for back-testing and analysis",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ─── middleware ------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.ALLOWED_ORIGINS.split(",") if cfg.ALLOWED_ORIGINS else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate-limit only if Redis is available
    try:
        if get_redis_cache():
            app.add_middleware(
                RateLimitMiddleware,
                default_limit_per_minute=cfg.RATE_LIMIT_PER_MINUTE,
            )
        else:
            log.warning(" Rate-limiting disabled – Redis not reachable")
    except Exception:
        log.warning(" Rate-limiting setup failed")

    # ─── include routers -----------------------------------------------
    from app.controller import (
        SymbolController as symbols,
        BacktestController as backtest,
        StrategyController as strategies,
        AnalyzeController as analyze,
        GridSearchController as grid_search,
        TaskController as tasks,
    )
    from app.graphql.index import graphql_app

    app.include_router(backtest.router,   prefix="/backtest",  tags=["Backtest"])
    app.include_router(analyze.router,    prefix="/analysis",  tags=["Analysis"])
    app.include_router(strategies.router, prefix="/strategy",  tags=["Strategy"])
    app.include_router(symbols.router,    prefix="/symbol",    tags=["Symbol"])
    app.include_router(grid_search.router,prefix="/gridsearch",tags=["GridSearch"])
    app.include_router(tasks.router,      prefix="/task",      tags=["Task"])
    app.mount("/graphql", graphql_app)

    # ─── health check -------------------------------------------------
    @app.get("/health", tags=["Meta"])
    async def health_check():
        try:
            await MongoDBConfig.get_master_client().admin.command("ping")
            mongo_state = "connected"
        except Exception:
            mongo_state = "error"
        return {"status": "healthy", "mongodb": mongo_state, "version": "alpha"}

    return app


# Entrypoint
app = create_app()
