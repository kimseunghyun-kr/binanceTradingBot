"""
Enhanced FastAPI Application with Security and GraphQL
──────────────────────────────────────────────────────────────────────────
Main application entry point with all middleware and routers configured.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.controller import (
    AnalyzeController,
    BacktestController,
    GridSearchController,
    StrategyController,
    SymbolController,
    TaskController,
    GraphQLController
)
from app.core.config import settings
from app.core.logger import setup_logger
from app.core.mongodb_config import mongodb_config
from app.core.security import (
    RateLimitMiddleware,
    SecurityHeaders,
    IPFilterMiddleware,
    RequestValidationMiddleware,
    get_cors_config
)
from app.services.orchestrator.OrchestratorService import OrchestratorService


# Setup logging
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting TradingBot API...")
    
    try:
        # Initialize MongoDB connections
        mongodb_config.initialize()
        await mongodb_config.ensure_indexes()
        
        # Validate connections
        connection_status = await mongodb_config.validate_connections()
        logger.info(f"MongoDB connection status: {connection_status}")
        
        # Initialize orchestrator service
        OrchestratorService.initialize()
        
        # Load initial data if needed
        # await load_initial_symbols()
        
        logger.info("TradingBot API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down TradingBot API...")
    
    # Cleanup resources
    OrchestratorService.cleanup()
    
    logger.info("TradingBot API shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="TradingBot API",
    description="Advanced cryptocurrency trading bot with backtesting and strategy optimization",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# Add middleware in correct order
# 1. Security headers (first)
app.add_middleware(SecurityHeaders)

# 2. Trusted host validation
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# 3. CORS
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# 4. GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 5. Request validation
app.add_middleware(RequestValidationMiddleware)

# 6. IP filtering (if configured)
if settings.IP_WHITELIST or settings.IP_BLACKLIST:
    app.add_middleware(
        IPFilterMiddleware,
        whitelist=settings.IP_WHITELIST,
        blacklist=settings.IP_BLACKLIST
    )

# 7. Rate limiting
app.add_middleware(RateLimitMiddleware, default_limit="100/minute")


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    try:
        # Check MongoDB connections
        connection_status = await mongodb_config.validate_connections()
        
        return {
            "status": "healthy",
            "version": "2.0.0",
            "mongodb": connection_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "TradingBot API",
        "version": "2.0.0",
        "description": "Advanced cryptocurrency trading bot",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "graphql": "/graphql",
            "health": "/health"
        }
    }


# Include routers
app.include_router(BacktestController.router, prefix="/api/v2")
app.include_router(AnalyzeController.router, prefix="/api/v2")
app.include_router(StrategyController.router, prefix="/api/v2")
app.include_router(SymbolController.router, prefix="/api/v2")
app.include_router(GridSearchController.router, prefix="/api/v2")
app.include_router(TaskController.router, prefix="/api/v2")
app.include_router(GraphQLController.router, prefix="/api/v2")


# Metrics endpoint for monitoring
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    # In production, use prometheus-client library
    return {
        "backtest_requests_total": 0,
        "backtest_duration_seconds": 0,
        "active_connections": 0,
        "mongodb_connections": 0
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )