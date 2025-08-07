@echo off
setlocal

echo =========================================
echo Stopping Binance Trading Bot Services
echo =========================================
echo.

REM Stop all services with both profiles
docker compose --profile db --profile app down

if %errorlevel% equ 0 (
    echo.
    echo All services stopped successfully!
) else (
    echo.
    echo Warning: Some services may not have stopped properly.
    echo You can check with: docker ps
)

echo.
pause