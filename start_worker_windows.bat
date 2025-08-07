@echo off
setlocal

echo Starting Celery Worker...
echo.
echo Press Ctrl+C to stop the worker
echo.

REM Start Celery worker with info level logging
python worker.py

endlocal