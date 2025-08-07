@echo off
setlocal enabledelayedexpansion

echo =========================================
echo Starting Binance Trading Bot with Docker Compose
echo =========================================
echo.

REM Check if .env.development exists
if not exist .env.development (
    if exist .env (
        echo Creating .env.development from .env...
        copy .env .env.development
    ) else (
        echo Warning: .env file not found. Please create .env.development with your configuration.
        echo.
    )
)

echo Starting services with profiles: db and app
echo This will start:
echo   - MongoDB ^(master ^& slave with replica set^)
echo   - Redis
echo   - PostgreSQL  
echo   - FastAPI application
echo   - Celery worker
echo   - Nginx proxy
echo.

REM Note: Windows Docker Desktop handles socket permissions automatically
REM No need for chmod 666 on Windows

REM Start all services with both profiles
docker compose --profile db --profile app up -d --build

if %errorlevel% neq 0 (
    echo.
    echo =========================================
    echo ERROR: Failed to start services!
    echo =========================================
    echo Please check:
    echo   1. Docker Desktop is running
    echo   2. No port conflicts ^(8000, 27017, 27018, 6379, 5432^)
    echo   3. Docker compose file is valid
    pause
    exit /b 1
)

echo.
echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check service status
echo.
echo Service Status:
echo ---------------
docker compose ps

echo.
echo =========================================
echo Services started successfully!
echo =========================================
echo.
echo Access points:
echo   - API: http://localhost:8000
echo   - Swagger UI: http://localhost:8000/docs
echo   - GraphQL: http://localhost:8000/graphql
echo   - Nginx Proxy: http://localhost:80
echo.
echo Commands:
echo   - View logs: docker compose logs -f [service_name]
echo   - Stop all: docker compose --profile db --profile app down
echo   - View running containers: docker ps
echo.

pause