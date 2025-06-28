@echo off
REM Start the required services
docker-compose up -d mongo postgres redis

REM Wait for MongoDB to be ready
:wait_mongo
powershell -Command "(New-Object Net.Sockets.TcpClient).Connect('localhost', 27017)" 2>NUL
if errorlevel 1 (
    echo Waiting for MongoDB...
    timeout /t 1 > NUL
    goto wait_mongo
)

REM Wait for Postgres to be ready
:wait_postgres
powershell -Command "(New-Object Net.Sockets.TcpClient).Connect('localhost', 5432)" 2>NUL
if errorlevel 1 (
    echo Waiting for Postgres...
    timeout /t 1 > NUL
    goto wait_postgres
)

REM Wait for Redis to be ready
:wait_redis
powershell -Command "(New-Object Net.Sockets.TcpClient).Connect('localhost', 6379)" 2>NUL
if errorlevel 1 (
    echo Waiting for Redis...
    timeout /t 1 > NUL
    goto wait_redis
)

REM Start FastAPI app
python run_local.py
