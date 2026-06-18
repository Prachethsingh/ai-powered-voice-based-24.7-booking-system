@echo off
REM Quick test of ai powered voice based 24.7 booking system on Windows
REM This tests the AI pipeline without external services

echo ============================================================
echo ai powered voice based 24.7 booking system - Windows Test
echo ============================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Install Python 3.10+ first.
    exit /b 1
)

echo Installing minimal dependencies...
pip install -q fastapi uvicorn loguru python-dotenv cryptography httpx pydantic

echo.
echo Running pipeline tests (fallback mode - no ML models needed)...
echo.

python call_simulator.py --batch

echo.
echo ============================================================
echo Test complete. Dashboard and telephony require Redis/Asterisk.
echo Install WSL2 with Docker for full functionality.
echo ============================================================