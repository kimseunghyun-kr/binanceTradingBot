@echo off
setlocal enabledelayedexpansion

echo Starting Binance Trading Bot services...

REM Start DB services in the background (if not already running)
docker compose up -d mongo postgres redis

echo Waiting for services to be ready...

REM Wait for MongoDB on port 27017
:wait_mongo
echo Checking MongoDB on port 27017...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27017 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for MongoDB...
    timeout /t 1 /nobreak >nul
    goto wait_mongo
)
echo MongoDB is ready!

REM Wait for PostgreSQL on port 5432
:wait_postgres
echo Checking PostgreSQL on port 5432...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 5432 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for PostgreSQL...
    timeout /t 1 /nobreak >nul
    goto wait_postgres
)
echo PostgreSQL is ready!

REM Wait for Redis on port 6379
:wait_redis
echo Checking Redis on port 6379...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for Redis...
    timeout /t 1 /nobreak >nul
    goto wait_redis
)
echo Redis is ready!

echo All services are ready! Starting FastAPI application...

REM Start FastAPI app
python run_local.py

endlocal