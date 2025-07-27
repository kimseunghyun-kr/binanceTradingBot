# Architecture Refactoring Summary

## Overview
This document summarizes the major architectural changes made to the Binance Trading Bot to implement proper separation of concerns, MongoDB master-slave architecture, and sandboxed strategy execution.

## Key Changes

### 1. MongoDB Master-Slave Architecture
- **File**: `app/core/db/mongodb_config.py`
- Implemented proper master-slave separation
- API layer writes to master, reads from slave
- Business logic layer (StrategyOrchestrator) only has read-only access to slave
- Automatic index creation and user management

### 2. FastAPI Application Structure
- **File**: `KwontBot.py`
- Proper lifespan management with async context manager
- MongoDB initialization during startup
- Security middleware integration (JWT, rate limiting, CORS)
- Health check endpoint added

### 3. Service Layer Updates
- **File**: `app/core/init_services.py`
- Refactored to use the new mongodb_config
- Global access functions for master/slave databases
- Proper async/sync client separation

### 4. OrchestratorService Integration
- **File**: `app/services/orchestrator/OrchestratorService.py`
- Updated to use read-only MongoDB URI for containers
- Proper Docker initialization and cleanup
- Redis caching integration

### 5. BackTestService Updates
- **File**: `app/services/BackTestService.py`
- Uses proper MongoDB clients (master for writes, slave for reads)
- Integrated with OrchestratorService for sandboxed execution
- Proper error handling and result enrichment

### 6. GraphQL Implementation
- **Files**: `app/graphql/schema.py`, `app/graphql/resolvers.py`
- Complete GraphQL API for symbol selection
- Vendor-agnostic querying without lock-in
- Proper separation of read/write operations
- Real-time subscriptions support

### 7. Celery Task Integration
- **File**: `app/tasks/BackTestTask.py`
- Async task execution for long-running backtests
- Progress tracking and status updates
- Proper error handling and database logging

### 8. Security Implementation
- **File**: `app/core/security.py`
- JWT authentication support
- Rate limiting middleware
- CORS configuration
- API key validation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          API Layer                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │   FastAPI   │  │   GraphQL    │  │   Celery Tasks     │    │
│  │  REST APIs  │  │   Queries    │  │   (Async Jobs)     │    │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘    │
│         │                 │                      │               │
│         └─────────────────┴──────────────────────┘              │
│                           │                                      │
│  ┌────────────────────────┴─────────────────────────────────┐   │
│  │                    Service Layer                          │   │
│  │  ┌───────────────┐  ┌─────────────┐  ┌───────────────┐  │   │
│  │  │ BackTestService│  │SymbolService│  │StrategyService│  │   │
│  │  └───────┬───────┘  └──────┬──────┘  └───────┬───────┘  │   │
│  └──────────┴──────────────────┴─────────────────┴──────────┘   │
│                                │                                 │
│  ┌─────────────────────────────┴────────────────────────────┐   │
│  │                    MongoDB Master                         │   │
│  │                  (Read/Write Access)                      │   │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Business Logic Layer                         │
│                    (Sandboxed Container)                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  StrategyOrchestrator.py                  │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │  │
│  │  │  Strategies │  │ Indicators   │  │ Portfolio Mgmt│   │  │
│  │  └─────────────┘  └──────────────┘  └───────────────┘   │  │
│  └───────────────────────────┬───────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                    MongoDB Slave                           │  │
│  │                  (Read-Only Access)                        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables
Add these to your `.env` file:

```env
# MongoDB Configuration
MONGO_URI_MASTER=mongodb://localhost:27017
MONGO_URI_SLAVE=mongodb://localhost:27018  # Optional, for replica set
MONGO_DB=trading
MONGODB_USERNAME=admin  # Optional
MONGODB_PASSWORD=password  # Optional

# Security
SECRET_KEY=your-secret-key-here
RATE_LIMIT_PER_MINUTE=100
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Redis
REDIS_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Keys
BINANCE_API_KEY=your-binance-key
BINANCE_API_SECRET=your-binance-secret
COINMARKETCAP_API_KEY=your-cmc-key
```

## Usage

### Starting the Application

```bash
# Start all services with Docker Compose
docker-compose up -d

# Or run locally
# 1. Start MongoDB
mongod --dbpath ./data/db

# 2. Start Redis
redis-server

# 3. Start Celery Worker
python worker.py

# 4. Start FastAPI Application
python KwontBot.py
```

### Testing the Architecture

```bash
# Run the test script
python test_architecture.py

# Or test individual components:
# 1. Health Check
curl http://localhost:8000/health

# 2. GraphQL Query
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ symbols(limit: 5) { symbol name price } }"}'

# 3. Run a Backtest
curl -X POST http://localhost:8000/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "SimpleMovingAverageStrategy",
    "symbols": ["BTCUSDT"],
    "interval": "1h",
    "num_iterations": 100
  }'
```

## Next Steps

1. **Production Deployment**
   - Set up MongoDB replica set for true master-slave replication
   - Configure proper authentication and SSL
   - Set up monitoring with Prometheus/Grafana

2. **Performance Optimization**
   - Implement connection pooling
   - Add caching layers for frequently accessed data
   - Optimize Docker image sizes

3. **Feature Enhancements**
   - Add more sophisticated trading strategies
   - Implement real-time data streaming
   - Add portfolio management features

## Troubleshooting

### Common Issues

1. **MongoDB Connection Errors**
   - Ensure MongoDB is running
   - Check connection strings in environment variables
   - Verify network connectivity

2. **Docker Issues**
   - Ensure Docker daemon is running
   - Check if orchestrator image is built
   - Verify volume permissions

3. **GraphQL Errors**
   - Check if all resolvers are properly implemented
   - Verify database schema matches GraphQL types
   - Check for missing imports

### Logs

- Application logs: `logs/app.log`
- MongoDB logs: Check MongoDB log location
- Docker logs: `docker logs <container_name>`
- Celery logs: Check Celery worker output