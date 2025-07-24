import logging
import os

from fastapi import FastAPI

from app.controller import (SymbolController as symbols,
                            BacktestController as backtest_v2,
                            StrategyController as strategies,
                            AnalyzeController as analyze,
                            GridSearchController as gridSearch,
                            TaskController as tasks
                            )
from app.core import init_services
from app.core.init_services import database, mongo_async

# Create FastAPI app
app = FastAPI(
    title="Trading Bot API",
    description="FastAPI service for trading bot backtesting and analysis",
    version="1.0.0"
)

# Logging configuration: write logs to file (and console if needed)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/app.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Include API routers
app.include_router(backtest_v2.router)
app.include_router(analyze.router)
app.include_router(strategies.router)
app.include_router(symbols.router)
app.include_router(gridSearch.router)
app.include_router(tasks.router)


# Startup and shutdown events for DB connections
@app.on_event("startup")
async def on_startup():
    # Connect to PostgreSQL if configured
    if database:
        try:
            await database.connect()
            logging.info("PostgreSQL connected.")
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
    else:
        logging.info("PostgreSQL not configured. Skipping DB connection.")
    # (MongoDB uses motor which connects on first operation, no explicit connect needed)
    # We could test Mongo connection here if desired:
    if mongo_async:
        try:
            # Ping MongoDB
            await mongo_async.server_info()
            logging.info("MongoDB connection verified.")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    # Disconnect from PostgreSQL
    if database:
        await database.disconnect()
        logging.info("PostgreSQL disconnected.")
    # Close MongoDB connection
    if mongo_async:
        mongo_async.close()
        logging.info("MongoDB client closed.")
