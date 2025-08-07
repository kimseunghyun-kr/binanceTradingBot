@echo off
setlocal enabledelayedexpansion

echo Starting Binance Trading Bot debug services (with MongoDB replica set)...

REM Start DB services in the background including mongo-init
docker compose up -d mongo-init postgres redis

echo Waiting for services to be ready...

REM Wait for MongoDB primary on port 27017
:wait_mongo1
echo Checking MongoDB primary on port 27017...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27017 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for MongoDB primary...
    timeout /t 1 /nobreak >nul
    goto wait_mongo1
)
echo MongoDB primary is ready!

REM Wait for MongoDB secondary on port 27018
:wait_mongo2
echo Checking MongoDB secondary on port 27018...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27018 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for MongoDB secondary...
    timeout /t 1 /nobreak >nul
    goto wait_mongo2
)
echo MongoDB secondary is ready!

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

echo All services are ready!
echo MongoDB replica set initialized with primary (27017) and secondary (27018)
echo You can now run 'python run_local.py' in another terminal or debug in your IDE

endlocal