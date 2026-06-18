@echo off
REM Windows runner for ai powered voice based 24.7 booking system
REM This runs the AI pipeline without Asterisk (telephony) and Redis
REM For full functionality, use WSL2 or a Linux VM

echo ============================================================
echo ai powered voice based 24.7 booking system - Windows Runner
echo ============================================================
echo.

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Install Python 3.10+ and add to PATH.
    exit /b 1
)

REM Install Python dependencies
echo Installing Python dependencies...
pip install -q fastapi uvicorn loguru python-dotenv cryptography redis pydantic httpx transformers peft trl datasets

REM Create directories
if not exist "database" mkdir database
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids
if not exist "exports" mkdir exports

REM Check if Redis is available (optional)
where redis-server >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo NOTE: Redis not found. Running without deduplication/rate limiting.
    echo       Install Redis for Windows or use WSL2 for full features.
    echo.
)

REM Start Python AI service
echo Starting Python AI service on port 8001...
start "Python-AI" /min powershell -Command "cd '%cd%'; python -m uvicorn backend.python.main:app --host 127.0.0.1 --port 8001 --workers 1"

timeout /t 3 /nobreak >nul

REM Start Node.js server
echo Starting Node.js server on port 8000...
cd backend\node
start "Node-Server" /min powershell -Command "cd '%cd%\..\..'; node server.js"
cd ..\..

timeout /t 2 /nobreak >nul

REM Start React dashboard
echo Starting React dashboard on port 3000...
cd frontend
start "React-Dev" /min powershell -Command "cd '%cd%'; npm run dev"
cd ..

echo.
echo ============================================================
echo Services starting...
echo ============================================================
echo Python AI    : http://localhost:8001
echo Node.js API  : http://localhost:8000
echo Dashboard    : http://localhost:3000
echo.
echo NOTE: Without Redis, deduplication and rate limiting are disabled.
echo       Without Asterisk, no actual phone calls will work.
echo.
echo Test the pipeline:
echo   python call_simulator.py
echo   python call_simulator.py --batch
echo.
echo To stop: close the PowerShell windows or run stop_all.bat