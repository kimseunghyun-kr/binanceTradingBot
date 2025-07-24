# Backtest Setup Guide

## Overview
The backtest system has been refactored to follow a controller-service-repository pattern. The following changes have been made:

1. **Controller**: Updated to use `BacktestControllerV2` with enhanced features
2. **Service**: `BackTestServiceV2` handles business logic with Docker orchestration support
3. **Task**: Celery task updated to match V2 controller expectations
4. **Test Endpoint**: Added `/backtest/submit-test` for testing without authentication

## Running a Single Backtest

### 1. Start Required Services

```bash
# Start Redis (required for Celery)
docker run -d -p 6379:6379 redis:latest

# Start MongoDB (required for data storage)
docker run -d -p 27017:27017 mongo:latest
```

### 2. Start the Application

In one terminal, start the FastAPI server:
```bash
python run_local.py
```

In another terminal, start the Celery worker:
```bash
python worker.py
```

### 3. Run a Test Backtest

Use the provided test script:
```bash
python test_backtest.py
```

Or make a direct API call:
```bash
curl -X POST http://localhost:8000/backtest/submit-test \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "peak_ema_reversal",
    "strategy_params": {
      "tp_ratio": 0.1,
      "sl_ratio": 0.05
    },
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "interval": "1h",
    "num_iterations": 100,
    "use_cache": false,
    "save_results": true
  }'
```

### 4. Check Results

Get task status:
```bash
curl http://localhost:8000/backtest/status/{task_id}
```

Get full results:
```bash
curl http://localhost:8000/backtest/results/{task_id}
```

## API Endpoints

- `POST /backtest/submit-test`: Submit backtest without authentication (for testing)
- `POST /backtest/submit`: Submit backtest with authentication
- `GET /backtest/status/{task_id}`: Get backtest status
- `GET /backtest/results/{task_id}`: Get full backtest results
- `WebSocket /backtest/stream/{task_id}`: Stream real-time progress

## Configuration

The system uses environment variables for configuration. Key settings:

- `MONGO_URI`: MongoDB connection string
- `REDIS_BROKER_URL`: Redis URL for Celery
- `SECRET_KEY`: JWT secret key
- `API_KEY`: API authentication key

See `app/core/pydanticConfig/settings.py` for all available settings.

## Architecture

```
Controller (FastAPI)
    ↓
Service Layer (Business Logic)
    ↓
Celery Task (Async Processing)
    ↓
Orchestrator Service (Docker Sandboxing)
    ↓
Strategy Execution
```

The system supports:
- Custom strategy code execution
- Symbol filtering
- Real-time progress streaming
- Result caching
- Multiple export formats

## Troubleshooting

1. **Connection Errors**: Ensure MongoDB and Redis are running
2. **Task Not Found**: Check Celery worker is running and connected
3. **Strategy Not Found**: Verify strategy exists in `entities/strategies/concreteStrategies/`
4. **Authentication Issues**: Use `/backtest/submit-test` endpoint for testing