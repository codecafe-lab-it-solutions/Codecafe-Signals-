@echo off
title Create Desktop Shortcut - CodeCafe Signals
cd /d "%~dp0"
echo Creating desktop shortcut for CodeCafe Signals Platform...

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" create_shortcut.py
) else (
    python create_shortcut.py
)

pause
