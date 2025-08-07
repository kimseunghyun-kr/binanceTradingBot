@echo off
setlocal

echo Stopping all Binance Trading Bot containers...

REM Stop and remove all containers
docker compose down

echo.
echo Cleaning up Docker resources...

REM Remove unused containers
docker container prune -f

REM Remove unused images
docker image prune -f

REM Remove unused volumes (be careful - this removes data!)
echo.
echo WARNING: The next command will remove unused Docker volumes.
echo This will DELETE data stored in unused volumes!
echo Press Ctrl+C now to cancel, or
pause

docker volume prune -f

echo.
echo Docker cleanup completed!
echo.

endlocal