# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Binance trading bot with a microservices architecture designed for backtesting and automated trading. The project uses FastAPI for the REST API, Celery for asynchronous task processing, Redis as message broker, and MongoDB/PostgreSQL for data storage.

**Current Status**: Early development. Recent refactoring completed:
- ✅ V2 Controller-Service architecture implemented
- ✅ Celery tasks updated to match V2 expectations
- ✅ Basic backtest execution functional
- ✅ Test endpoints available for development

## Common Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start FastAPI server with hot reload
python run_local.py

# Start Celery worker
python worker.py

# Run tests
pytest

# Run tests with coverage
pytest --cov
```

### Docker Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Code Quality
```bash
# Format code
black .

# Type checking
mypy .

# Linting
flake8
```

## Architecture Overview

### Core Components

1. **API Layer** (`app/controller/`): FastAPI endpoints handle HTTP requests for backtesting, analysis, and strategy management.

2. **Service Layer** (`app/services/`): Business logic implementation that processes requests from controllers.

3. **Task Queue** (`app/tasks/`): Celery tasks handle computationally intensive operations like backtesting and optimization asynchronously.

4. **Trading Engine** (`entities/`):
   - `strategies/`: Trading strategy implementations (PeakEmaReversal, MomentumStrategy, EnsembleStrategy)
   - `portfolio/`: Position management and risk control
   - `tradeManager/`: Trade execution logic with multi-leg entry/exit support
   - `perpetuals/`: Perpetual futures specific logic including funding rates

5. **Market Data** (`app/marketDataApi/`): Integration with Binance API and CoinMarketCap for market data.

6. **Technical Indicators** (`app/indicators/`): Custom implementations including EMA, Fibonacci, Volume Profile.

### Key Design Patterns

1. **Asynchronous Processing**: Long-running backtests are queued as Celery tasks, allowing the API to return immediately with a task ID.

2. **Configuration Management**: Uses Pydantic settings with environment variables for type-safe configuration across different environments.

3. **Strategy Pattern**: Trading strategies implement a common interface, allowing easy addition of new strategies.

4. **Multi-Asset Synchronization**: Global clock driver ensures events are properly synchronized across multiple trading pairs.

### Critical Files to Understand

- `app/core/pydanticConfig/settings.py`: Central configuration management
- `app/controller/BacktestController.py`: V2 backtest endpoints with WebSocket support
- `app/services/BackTestService.py`: V2 service layer with Docker orchestration
- `app/tasks/BackTestTask.py`: Updated Celery task for V2 architecture
- `entities/strategies/base_strategy.py`: Base class for all trading strategies
- `entities/portfolio/portfolio.py`: Portfolio management and risk calculations

### Recent Architectural Changes

- **2025-07-24**: Refactored to V2 Controller-Service architecture
  - Updated `BacktestController.py` to V2 with streaming support
  - Modified `BackTestTask.py` to handle V2 task payloads
  - Added test endpoint `/backtest/submit-test` for development
  - Fixed `KwontBot.py` to use V2 controller
- Previous changes:
  - Moved from simple TP/SL to flexible exit resolver hooks
  - Implemented crossing policy for simultaneous TP/SL hits
  - Added single-pass cost model for accurate fee calculations
  - Enhanced capacity and sizing models as first-class entities

## Development Notes

- The project uses environment files (`.env`, `.env.development`, `.env.production`) for configuration
- MongoDB is the primary database for storing backtest results and trading data
- Redis serves as both Celery broker and result backend
- The API documentation is available at http://127.0.0.1:8000/docs when running locally
- Strategy parameters are configured in `app/inputconfig/config.yml`

## Testing Backtest Execution

For quick testing without authentication:
```bash
# 1. Start services
python run_local.py  # Terminal 1
python worker.py     # Terminal 2

# 2. Run test
python test_backtest.py
```

Or use the test endpoint directly:
```bash
curl -X POST http://localhost:8000/backtest/submit-test \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "peak_ema_reversal", "symbols": ["BTCUSDT"], "interval": "1h", "num_iterations": 10}'
```