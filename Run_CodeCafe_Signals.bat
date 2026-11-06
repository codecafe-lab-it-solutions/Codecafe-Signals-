@echo off
title CodeCafe Signals - Autonomous AI Trading Platform
color 0b
cls
echo ============================================================
echo      CODECAFE SIGNALS - AUTONOMOUS TRADING PLATFORM
echo ============================================================
echo.
echo  Starting platform services...
echo  Your browser will open automatically in 2 seconds.
echo.

cd /d "%~dp0"

:: Check virtual environment python
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" dashboard_server.py
    goto :end
)

:: Check uv
where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv run python dashboard_server.py
    goto :end
)

:: Fallback to system python
where python >nul 2>nul
if %errorlevel% equ 0 (
    python dashboard_server.py
    goto :end
)

echo [ERROR] Python not found. Please ensure Python or uv is installed.
pause

:end

