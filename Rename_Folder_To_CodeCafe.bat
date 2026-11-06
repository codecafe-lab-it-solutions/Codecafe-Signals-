@echo off
rem One-time: rename "O:\Projects\Yo Signals" to "O:\Projects\CodeCafe Signals" and rebuild the Python environment.
rem Run it AFTER fully closing Claude (and any terminal, editor or Explorer window open inside this folder).
if not "%~1"=="--from-temp" (
    copy /y "%~f0" "%TEMP%\codecafe_rename.bat" >nul
    start "Rename to CodeCafe Signals" "%TEMP%\codecafe_rename.bat" --from-temp
    exit /b
)
title Rename to CodeCafe Signals
cd /d O:\Projects
rem stop only this project's python/uv processes (dashboard, MCP servers), nothing else
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|uv)' -and $_.CommandLine -match 'Yo Signals' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 >nul
ren "O:\Projects\Yo Signals" "CodeCafe Signals"
if errorlevel 1 (
    echo.
    echo [ERROR] Rename failed: something still has the folder open.
    echo Close Claude, VS Code, terminals and Explorer windows inside "O:\Projects\Yo Signals", then run this again.
    pause
    exit /b 1
)
cd /d "O:\Projects\CodeCafe Signals"
echo Rebuilding the Python environment for the new folder path...
rmdir /s /q .venv
uv sync
del "Rename_Folder_To_CodeCafe.bat"
echo.
echo ============================================================
echo  Done. Project is now at: O:\Projects\CodeCafe Signals
echo  1. Open Claude in that folder.
echo  2. Start the app with Run_CodeCafe_Signals.bat
echo ============================================================
pause
