@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Checking Binance Trading Bot Services
echo ========================================
echo.

echo [Docker Status]
docker --version
docker compose version
echo.

echo [Running Containers]
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.

echo [Service Health Check]
echo -----------------------

REM Check MongoDB
echo Checking MongoDB (port 27017)...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27017 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] MongoDB is running on port 27017
) else (
    echo [FAIL] MongoDB is NOT running on port 27017
)

REM Check MongoDB Secondary (if exists)
echo Checking MongoDB Secondary (port 27018)...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27018 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] MongoDB Secondary is running on port 27018
) else (
    echo [INFO] MongoDB Secondary is not running (only needed in debug mode)
)

REM Check PostgreSQL
echo Checking PostgreSQL (port 5432)...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 5432 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL is running on port 5432
) else (
    echo [FAIL] PostgreSQL is NOT running on port 5432
)

REM Check Redis
echo Checking Redis (port 6379)...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Redis is running on port 6379
) else (
    echo [FAIL] Redis is NOT running on port 6379
)

REM Check FastAPI
echo Checking FastAPI (port 8000)...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FastAPI is running on port 8000
    echo.
    echo API Endpoints:
    echo - Swagger UI: http://localhost:8000/docs
    echo - ReDoc: http://localhost:8000/redoc
    echo - GraphQL: http://localhost:8000/graphql
) else (
    echo [INFO] FastAPI is not running on port 8000
)

echo.
echo ========================================
echo Check Complete
echo ========================================

endlocal