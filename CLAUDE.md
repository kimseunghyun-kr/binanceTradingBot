# Binance Trading Bot - Development Guide

A FastAPI + Celery-based backtesting platform for trading strategies on Binance.

## Quick Start

### With Nix (Recommended)

```bash
# 1. Enter the Nix development shell (sets up Python 3.12 + UV)
nix develop

# 2. Create and activate virtual environment
uv venv
source .venv/bin/activate

# 3. Install Python dependencies
uv pip install -r requirements.txt

# 4. Start infrastructure services
docker compose up -d mongo redis postgres

# 5. Start FastAPI server (Terminal 1)
python run_local.py

# 6. Start Celery worker (Terminal 2)
python worker.py
```

### Without Nix

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3-6. Same as above (docker compose, run_local.py, worker.py)
```

### Full Docker Stack

```bash
docker compose up
```

This starts all services:
- FastAPI at http://localhost:8000
- MongoDB on port 27017
- PostgreSQL on port 5432
- Redis on port 6379
- Nginx reverse proxy on port 80

## Access Points

| Endpoint | Description |
|----------|-------------|
| http://127.0.0.1:8000/ | Backtest UI (Frontend) |
| http://127.0.0.1:8000/docs | API Documentation (Swagger UI) |
| POST `/backtest` | Submit a backtest |
| GET `/tasks/{task_id}` | Check task status |

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

## API Usage

### Submit a Backtest

```bash
curl -X POST http://127.0.0.1:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": {"name": "peak_ema_reversal", "params": {}},
    "symbols": ["BTCUSDT"],
    "timeframe": "1d"
  }'
```

### Check Task Status

```bash
curl http://127.0.0.1:8000/tasks/{task_id}
```

### Available Strategies

| Name | Description |
|------|-------------|
| `peak_ema_reversal` | Single-peak detection with EMA pullback |
| `momentum` | Simple momentum strategy |
| `ensemble` | Combine multiple strategies |

### Timeframes

- `1d` (daily) - default
- `1w` (weekly)

## Project Structure

```
├── KwontBot.py              # Main FastAPI app entry point
├── run_local.py             # Local server launcher
├── worker.py                # Celery worker launcher
├── static/
│   └── index.html           # Backtest UI (served at /)
├── app/
│   ├── controller/          # API endpoints (FastAPI routers)
│   ├── services/            # Business logic
│   ├── tasks/               # Celery background tasks
│   ├── strategies/          # Trading strategy implementations
│   ├── dto/                 # Request/Response models
│   ├── marketDataApi/       # Binance/CoinMarketCap API clients
│   ├── core/                # Database & Celery configuration
│   └── pydanticConfig/      # Settings & environment config
├── flake.nix                # Nix flake for reproducible dev environment
├── flake.lock               # Locked Nix dependency versions
├── .envrc                   # Auto-load Nix environment with direnv
└── docker-compose.yml       # Infrastructure services
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
