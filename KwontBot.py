import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controller import (
    SymbolController as symbols,
    BacktestController as backtest,
    StrategyController as strategies,
    AnalyzeController as analyze,
    GridSearchController as grid_search,
    TaskController as tasks,
)
from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import (
    _init_external_services,   # already called on import, safe idempotent
)
from app.core.pydanticConfig.settings import get_settings
from app.core.security import RateLimitMiddleware
from app.graphql.index import graphql_app

# ─── logging -----------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ─── global config ------------------------------------------------------
cfg = get_settings()
MongoDBConfig.initialize()      # build pools
_init_external_services()       # Postgres / Redis

# ─── lifespan ----------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🔧 FastAPI startup")

    # expose pools & settings to routes
    app.mongo_async = MongoDBConfig.get_master_client()
    app.mongo_sync  = MongoDBConfig.get_master_client_sync()
    app.mongo_ro_uri = MongoDBConfig.get_read_only_uri()
    app.settings = cfg

    try:
        yield
    finally:
        MongoDBConfig.close()
        log.info("FastAPI shutdown")


# ─── FastAPI app -------------------------------------------------------
app = FastAPI(
    title="Trading Bot API",
    description="FastAPI service for back-testing and analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── middleware --------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.ALLOWED_ORIGINS.split(",") if cfg.ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=cfg.RATE_LIMIT_PER_MINUTE,
)

# ─── routers -----------------------------------------------------------
app.include_router(backtest.router,   prefix="/backtest",  tags=["Backtest"])
app.include_router(analyze.router,    prefix="/analysis",  tags=["Analysis"])
app.include_router(strategies.router, prefix="/strategy",  tags=["Strategy"])
app.include_router(symbols.router,    prefix="/symbol",    tags=["Symbol"])
app.include_router(grid_search.router,prefix="/gridsearch",tags=["GridSearch"])
app.include_router(tasks.router,      prefix="/task",      tags=["Task"])
app.mount("/graphql", graphql_app)

# ─── health check ------------------------------------------------------
@app.get("/health", tags=["Meta"])
async def health_check():
    return {
        "status": "healthy",
        "mongodb": "connected" if MongoDBConfig.get_master_client() else "disconnected",
        "version": "alpha",
    }
