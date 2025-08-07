@echo off
setlocal enabledelayedexpansion

echo =========================================
echo Starting Development Environment (DB only)
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

echo Starting database services only (profile: db)
echo This will start:
echo   - MongoDB master ^(port 27017^)
echo   - MongoDB slave ^(port 27018^)
echo   - Redis ^(port 6379^)
echo   - PostgreSQL ^(port 5432^)
echo   - Mongo replica set initialization
echo.

REM Start DB services only
docker compose --profile db up -d

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start database services!
    echo Please check Docker Desktop is running.
    pause
    exit /b 1
)

echo.
echo Waiting for databases to be ready...
timeout /t 8 /nobreak >nul

echo.
echo Database Status:
echo ----------------
docker compose --profile db ps

echo.
echo =========================================
echo Database services ready for development!
echo =========================================
echo.
echo Now you can run locally:
echo   1. Start Celery Worker: python worker.py
echo   2. Start FastAPI: python run_local.py
echo.
echo MongoDB replica set is automatically initialized.
echo.
echo To stop databases: docker compose --profile db down
echo.

pause