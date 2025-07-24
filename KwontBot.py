import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controller import (SymbolController as symbols,
                            BacktestController as backtest,
                            StrategyController as strategies,
                            AnalyzeController as analyze,
                            GridSearchController as gridSearch,
                            TaskController as tasks
                            )
from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.core.security import (
    RateLimitMiddleware
)
from app.graphql.index import graphql_app

# Logging configuration: write logs to file (and console if needed)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize settings
settings = get_settings()

# Initialize MongoDB configuration
mongodb_config = MongoDBConfig(
    master_uri=settings.master_mongodb_uri,
    master_db_name=settings.mongo_db,
    master_username=settings.mongodb_username,
    master_password=settings.mongodb_password
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting up application...")
    try:
        # Initialize MongoDB connections
        await mongodb_config.initialize()
        logger.info("MongoDB initialized successfully")
        
        # Set mongodb_config in init_services for global access
        from app.core.init_services import set_mongodb_config
        set_mongodb_config(mongodb_config)
        
        # Initialize OrchestratorService for Docker-based strategy execution
        from app.services.orchestrator.OrchestratorService import OrchestratorService
        try:
            OrchestratorService.initialize()
            logger.info("OrchestratorService initialized successfully")
        except Exception as e:
            logger.warning(f"OrchestratorService initialization failed (Docker may not be available): {e}")
        
        # Store mongodb_config and settings in app state for access in routes
        app.state.mongodb_config = mongodb_config
        app.state.settings = settings
        
        # Get async clients for the app
        app.state.master_db = await mongodb_config.get_master_db_async()
        app.state.read_db = await mongodb_config.get_read_db_async()
        
        yield
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        
        # Cleanup OrchestratorService
        try:
            OrchestratorService.cleanup()
            logger.info("OrchestratorService cleaned up")
        except Exception as e:
            logger.error(f"OrchestratorService cleanup failed: {e}")
        
        # Close MongoDB connections
        await mongodb_config.close()
        logger.info("MongoDB connections closed")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Trading Bot API",
    description="FastAPI service for trading bot backtesting and analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Setup security middleware
# TODO

# Add CORS middleware after security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_per_minute
)

# Include API routers
app.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
app.include_router(analyze.router, prefix="/analysis", tags=["Analysis"])
app.include_router(strategies.router, prefix="/strategy", tags=["Strategy"])
app.include_router(symbols.router, prefix="/symbol", tags=["Symbol"])
app.include_router(gridSearch.router, prefix="/gridsearch", tags=["GridSearch"])
app.include_router(tasks.router, prefix="/task", tags=["Task"])

# Mount GraphQL app
app.mount("/graphql", graphql_app)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mongodb": "connected" if app.state.mongodb_config else "disconnected",
        "version": app.version
    }
