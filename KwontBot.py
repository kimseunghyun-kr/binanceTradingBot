import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.controller import (SymbolController as symbols,
                            BacktestController as backtest,
                            StrategyController as strategies,
                            AnalyzeController as analyze,
                            GridSearchController as gridSearch,
                            TaskController as tasks
                            )
from app.core import db

# Create FastAPI app
app = FastAPI(
    title="Trading Bot API",
    description="FastAPI service for trading bot backtesting and analysis",
    version="1.0.0"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging configuration: write logs to file (and console if needed)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/app.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Include API routers
app.include_router(backtest.router)
app.include_router(analyze.router)
app.include_router(strategies.router)
app.include_router(symbols.router)
app.include_router(gridSearch.router)

app.include_router(tasks.router)

# Serve static files (frontend UI)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the frontend UI at root path."""
        return FileResponse(static_dir / "index.html")


# Startup and shutdown events for DB connections
@app.on_event("startup")
async def on_startup():
    # Connect to PostgreSQL if configured
    if db.database:
        try:
            await db.database.connect()
            logging.info("PostgreSQL connected.")
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
    else:
        logging.info("PostgreSQL not configured. Skipping DB connection.")
    # (MongoDB uses motor which connects on first operation, no explicit connect needed)
    # We could test Mongo connection here if desired:
    if db.mongo_client:
        try:
            # Ping MongoDB
            await db.mongo_client.server_info()
            logging.info("MongoDB connection verified.")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    # Disconnect from PostgreSQL
    if db.database:
        await db.database.disconnect()
        logging.info("PostgreSQL disconnected.")
    # Close MongoDB connection
    if db.mongo_client:
        db.mongo_client.close()
        logging.info("MongoDB client closed.")
