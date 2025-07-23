# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Start all services (Redis, MongoDB, PostgreSQL) and API server
./run_local.sh

# Start services only (for debugging)
./run_local_debug.sh

# Windows users
run_local_windows.bat

# Direct Python execution
python run_local.py  # Starts FastAPI server on http://127.0.0.1:8000
python worker.py     # Starts Celery worker for background tasks
```

### Docker Operations
```bash
# Start all services with Docker Compose
docker compose up -d

# Start specific services
docker compose up -d mongo postgres redis

# View logs
docker compose logs -f app worker
```

### Testing
```bash
# Run tests (when implemented)
pytest

# Run specific test file
pytest tests/test_backtest.py
```

## Architecture Overview

This is a **FastAPI + Celery** based trading bot backtesting platform with the following core components:

### API Layer (FastAPI)
- **Entry Point**: `KwontBot.py` - Main FastAPI application
- **Controllers**: Located in `app/controller/` - Handle HTTP endpoints
  - `BacktestController` - Submit backtest jobs
  - `AnalyzeController` - Analysis endpoints
  - `StrategyController` - Strategy management
  - `SymbolController` - Symbol filtering/querying
  - `GridSearchController` - Parameter optimization
  - `TaskController` - Task status/results

### Task Processing (Celery)
- **Worker Entry**: `worker.py` - Celery worker process
- **Task Definitions**: `app/tasks/` - All async tasks
  - Tasks are auto-discovered by Celery
  - Main tasks: BackTestTask, AnalysisTask, GridSearchTask
- **Broker**: Redis (default: `redis://localhost:6379/0`)

### Data Layer
- **MongoDB**: Time series data, backtest results
  - Accessed via Motor (async) in API, PyMongo in workers
- **PostgreSQL**: Structured data (optional, for future use)
- **Redis**: Task queue and result backend

### Business Logic
- **Strategies**: `entities/strategies/` - Base and concrete strategy implementations
  - `BaseStrategy` - Abstract base class
  - Concrete strategies in `concreteStrategies/`
- **Portfolio Management**: `entities/portfolio/` and `entities/perpetuals/portfolio/`
  - Position tracking, margin calculations, P&L
- **Trade Management**: `entities/tradeManager/`
  - Order execution simulation, fill policies

### Services Layer
- **Core Services**: `app/services/`
  - `BackTestService` - Main backtest engine
  - `StrategyService` - Strategy execution
  - `PortFolioAnalysisService` - Performance analytics

## Key Workflows

### Submitting a Backtest
1. POST to `/backtest` with strategy parameters
2. Controller creates Celery task via `BackTestTask`
3. Task runs in worker, saves results to MongoDB
4. Poll `/tasks/{task_id}` for status/results

### Adding a New Strategy
1. Create new class in `entities/strategies/concreteStrategies/`
2. Inherit from `BaseStrategy` or `ParameterisedStrategy`
3. Implement required methods: `generate_signals()`, `get_parameters()`
4. Register in strategy service if needed

## Environment Configuration

The project uses profile-based configuration:
- `.env` - Default configuration
- `.env.development` - Development overrides
- `.env.production` - Production settings

Key environment variables:
- `MONGO_URI` - MongoDB connection string
- `REDIS_BROKER_URL` - Redis URL for Celery
- `BINANCE_API_KEY/SECRET` - Exchange credentials
- `COINMARKETCAP_API_KEY` - Market data API

## Important Notes

- **Project Status**: Pre-alpha, core functionality working but not production-ready
- **Symbol Filtering**: Currently static, dynamic query feature under development
- **Debugging**: Run `worker.py` in IDE to debug task execution
- **Logs**: Check `logs/app.log` and `logs/worker.log` for debugging