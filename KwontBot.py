import os, logging
from fastapi import FastAPI
from app.controller import (SymbolController as symbols,
                            BacktestController as backtest,
                            StrategyController as strategies,
                            AnalyzeController as analyze,
                            GridSearchController as gridSearch
                            )
from app.core import db

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
app.include_router(backtest.router)
app.include_router(analyze.router)
app.include_router(strategies.router)
app.include_router(symbols.router)

app.include_router(gridSearch.router)


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
