# Binance Trading Bot — FastAPI + Celery Backtesting Platform

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-async-green) ![Celery](https://img.shields.io/badge/Celery-5.x-yellow) ![Docker](https://img.shields.io/badge/Docker-orchestration-blue)

## Overview

This project is a robust, modular backtesting platform for trading strategies on Binance. It features a microservices architecture with **FastAPI** for REST API endpoints, **Celery** for distributed task processing, **Docker** for strategy sandboxing, and **MongoDB/Redis** for data persistence.

> **⚠️ Project Status: Early Development**
>
> Core functionality is working but still in active development. The controller-service architecture has been refactored and basic backtesting is functional.

### Technology Stack
* **Backend:** Python 3.10+, FastAPI, Celery
* **Databases:** MongoDB (primary), Redis (cache/broker), PostgreSQL (optional)
* **Container:** Docker (strategy sandboxing)
* **Libraries:** Pandas, NumPy, Pydantic, Motor (async MongoDB)

### Key Features
* ✅ **V2 Architecture:** Enhanced controller-service pattern with clean separation of concerns
* ✅ **Async Processing:** Celery-based task queue for long-running backtests
* ✅ **Strategy Sandboxing:** Docker-based isolation for custom strategy execution
* ✅ **Real-time Progress:** WebSocket support for streaming backtest progress
* ✅ **Multi-Asset Support:** Synchronized backtesting across multiple trading pairs
* ✅ **Flexible Exit Strategies:** Support for TP/SL with crossing policies
* ✅ **REST API:** Full Swagger/OpenAPI documentation
* 🚧 **GraphQL API:** Query interface for advanced filtering (in development)

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│   Service   │────▶│   Celery    │
│ Controller  │     │    Layer    │     │    Tasks    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   MongoDB   │     │    Redis    │     │   Docker    │
│   (Data)    │     │   (Cache)   │     │ (Sandbox)   │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Features & Project Status

### ✅ Working Features
* **V2 Backtest Controller:** Enhanced endpoints with authentication and streaming
* **Celery Task System:** Async task processing with progress tracking
* **Service Layer:** Business logic with Docker orchestration support
* **MongoDB Integration:** Data persistence with master-slave architecture
* **Strategy Execution:** Multiple built-in strategies (PeakEmaReversal, Momentum, Ensemble)
* **Test Endpoints:** Authentication-free endpoints for development

### 🚧 In Development
* **GraphQL API:** Advanced symbol filtering and queries
* **Production Authentication:** Full JWT-based auth system
* **Advanced Analytics:** Performance metrics and visualization
* **Live Trading:** Real-time trading execution (planned)

## Quick Start

### Prerequisites

* Python 3.10+
* Docker (for strategy sandboxing)
* Redis (message broker)
* MongoDB (data storage)

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/binanceTradingBot.git
cd binanceTradingBot
pip install -r requirements.txt
```

### 2. Start Required Services

```bash
# Using Docker
docker-compose up -d redis mongodb

# Or manually
docker run -d -p 6379:6379 redis:latest
docker run -d -p 27017:27017 mongo:latest
```

### 3. Configure Environment

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your settings
```

Key settings:
- `MONGO_URI`: MongoDB connection string
- `REDIS_BROKER_URL`: Redis URL for Celery
- `SECRET_KEY`: JWT secret (for production)
- `API_KEY`: API authentication key

### 4. Start the Application

**Terminal 1 - API Server:**
```bash
python run_local.py
# API docs available at http://localhost:8000/docs
```

**Terminal 2 - Celery Worker:**
```bash
python worker.py
```

### 5. Run Your First Backtest

**Option 1: Using the test script**
```bash
python test_backtest.py
```

**Option 2: Direct API call**
```bash
curl -X POST http://localhost:8000/backtest/submit-test \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "peak_ema_reversal",
    "strategy_params": {"tp_ratio": 0.1, "sl_ratio": 0.05},
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "interval": "1h",
    "num_iterations": 100
  }'
```

**Option 3: Using Swagger UI**
1. Open http://localhost:8000/docs
2. Navigate to `/backtest/submit-test`
3. Try it out with sample parameters

### 6. Check Results

```bash
# Get task status
curl http://localhost:8000/backtest/status/{task_id}

# Get full results
curl http://localhost:8000/backtest/results/{task_id}
```

## API Endpoints

### Backtest V2 Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|--------------|
| POST | `/backtest/submit` | Submit backtest with auth | Yes |
| POST | `/backtest/submit-test` | Submit backtest (test) | No |
| GET | `/backtest/status/{task_id}` | Get task status | Yes |
| GET | `/backtest/results/{task_id}` | Get full results | Yes |
| WS | `/backtest/stream/{task_id}` | Stream progress | No |
| POST | `/backtest/cancel/{task_id}` | Cancel running backtest | Yes |
| GET | `/backtest/export/{task_id}` | Export results | Yes |

### Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/symbols/binance` | Get all USDT pairs |
| GET | `/symbols/cmc` | Filter by market cap |
| GET | `/strategies` | List all strategies |
| POST | `/strategies/upload` | Upload custom strategy |
| GET | `/tasks/{task_id}` | Generic task status |

## Configuration

### Strategy Configuration (`app/inputconfig/config.yml`)

```yaml
strategy:
  name: peak_ema_reversal
  params:
    tp_ratio: 0.1
    sl_ratio: 0.05

backtest:
  timeframe: 1h
  num_iterations: 100
  initial_capital: 10000
  position_size_pct: 5.0
```

### Environment Variables

See `app/core/pydanticConfig/settings.py` for all available settings:

- **Database:** `MONGO_URI`, `REDIS_BROKER_URL`, `POSTGRES_DSN`
- **API Keys:** `BINANCE_API_KEY`, `COINMARKETCAP_API_KEY`
- **Security:** `SECRET_KEY`, `API_KEY`, `ALLOWED_ORIGINS`
- **Performance:** `ORCHESTRATOR_POOL_SIZE`, `BACKTEST_MAX_SYMBOLS`

## Project Structure

```
binanceTradingBot/
├── app/
│   ├── controller/          # FastAPI endpoints (V2 architecture)
│   │   ├── BacktestController.py    # V2 backtest endpoints
│   │   ├── StrategyController.py    # Strategy management
│   │   └── SymbolController.py      # Symbol filtering
│   ├── services/           # Business logic layer
│   │   ├── BackTestService.py       # V2 backtest service
│   │   ├── OrchestratorService.py   # Docker orchestration
│   │   └── StrategyService.py       # Strategy factory
│   ├── tasks/              # Celery async tasks
│   │   └── BackTestTask.py          # Backtest execution
│   ├── core/               # Core configuration
│   │   ├── celery_app.py            # Celery setup
│   │   ├── mongodb_config.py        # MongoDB master-slave
│   │   ├── security.py              # Auth & middleware
│   │   └── pydanticConfig/          # Settings management
│   └── marketDataApi/      # External API integrations
├── entities/               # Domain models (DO NOT MODIFY)
│   ├── strategies/         # Trading strategies
│   ├── portfolio/          # Portfolio management
│   └── tradeManager/       # Trade execution
├── StrategyOrchestrator/   # Docker sandbox (DO NOT MODIFY)
├── test_backtest.py        # Test script
├── run_local.py           # FastAPI entry point
├── worker.py              # Celery worker entry point
└── docker-compose.yml     # Service orchestration
```

## Development Guide

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test
pytest tests/test_backtest.py
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

### Debugging Tips

1. **API Debugging:**
   - Use FastAPI's automatic `/docs` for testing endpoints
   - Check logs in `logs/app.log`

2. **Celery Debugging:**
   - Run worker with `--loglevel=DEBUG`
   - Set breakpoints in task code
   - Check MongoDB for task progress

3. **Docker Debugging:**
   - Check orchestrator logs: `docker logs <container_id>`
   - Monitor pool status: `GET /backtest/pool/status`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Ensure MongoDB/Redis are running |
| Task not found | Restart Celery worker |
| Strategy not found | Check strategy exists in `entities/strategies/` |
| Authentication error | Use `/submit-test` endpoint for testing |
| Docker errors | Ensure Docker daemon is running |

## Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker=3
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add type hints to all functions
- Write tests for new features
- Update documentation
- Don't modify `entities/` or `StrategyOrchestrator/` without discussion

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with FastAPI, Celery, and Docker
- Inspired by professional trading systems
- Community contributions welcome!

---

**Happy Trading! 🚀**
