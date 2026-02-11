# Binance Trading Bot - Development Guide

This is a FastAPI + Celery-based backtesting platform for trading strategies on Binance.

## Quick Start with Nix (Recommended)

If you have Nix installed with flakes enabled:

```bash
# Enter the development shell (sets up Python 3.12 + UV automatically)
nix develop

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Start infrastructure services
docker-compose up -d mongo redis postgres

# In separate terminals:
python run_local.py   # FastAPI server (http://127.0.0.1:8000/docs)
python worker.py      # Celery worker
```

## Quick Start without Nix

```bash
# Ensure Python 3.9+ and pip/uv are installed
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Start infrastructure
docker-compose up -d mongo redis postgres

# Run the application
python run_local.py   # FastAPI server
python worker.py      # Celery worker (separate terminal)
```

## Project Structure

```
├── KwontBot.py              # Main FastAPI app entry point
├── run_local.py             # Local server launcher
├── worker.py                # Celery worker launcher
├── app/
│   ├── controller/          # API endpoints (FastAPI routers)
│   ├── services/            # Business logic
│   ├── tasks/               # Celery background tasks
│   ├── strategies/          # Trading strategy implementations
│   ├── marketDataApi/       # Binance/CoinMarketCap API clients
│   ├── core/                # Database & Celery configuration
│   └── pydanticConfig/      # Settings & environment config
├── flake.nix                # Nix flake for reproducible dev environment
└── docker-compose.yml       # Infrastructure services
```

## Configuration

Create a `.env` file (or `.env.development` for dev profile):

```env
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
COINMARKETCAP_API_KEY=your_key

MONGO_URI=mongodb://localhost:27017/trading
MONGO_DATABASE=trading
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/trading
REDIS_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Running with Docker (Full Stack)

```bash
docker-compose up
```

This starts all services:
- FastAPI at http://localhost:8000
- MongoDB on port 27017
- PostgreSQL on port 5432
- Redis on port 6379
- Nginx reverse proxy on port 80

## API Usage

1. **Submit a backtest:**
   ```bash
   curl -X POST http://127.0.0.1:8000/backtest \
     -H "Content-Type: application/json" \
     -d '{
       "strategy": {"name": "peak_ema_reversal", "params": {}},
       "symbols": ["BTCUSDT"],
       "timeframe": "1w"
     }'
   ```

2. **Check task status:**
   ```bash
   curl http://127.0.0.1:8000/tasks/{task_id}
   ```

## Development Commands

```bash
# Run tests
pytest

# Run with auto-reload
uvicorn KwontBot:app --reload --host 127.0.0.1 --port 8000

# Run Celery worker with debug logging
celery -A app.core.celery_app worker --loglevel=DEBUG
```

## Tech Stack

- **Framework:** FastAPI
- **Task Queue:** Celery with Redis broker
- **Databases:** MongoDB (OHLCV data, results), PostgreSQL (optional), Redis (caching)
- **APIs:** Binance, CoinMarketCap
- **Data:** pandas, numpy, matplotlib, mplfinance

