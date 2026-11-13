@echo off
title A^&D Thysia Resort Management System
cd /d "%~dp0"

echo ========================================================
echo    Starting A^&D Thysia Resort Management System...
echo ========================================================
echo.
echo Server starting at http://127.0.0.1:5000
echo Opening browser in 2 seconds...
echo Press Ctrl+C in this window to stop the server.
echo.

:: Automatically open default browser after a short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

:: Launch project using Python (system environment where all packages are installed)
python run.py

if errorlevel 1 (
    echo.
    echo ========================================================
    echo Server encountered an error and stopped.
    echo ========================================================
)

echo.
pause
