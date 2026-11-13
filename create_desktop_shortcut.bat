@echo off
title Create Desktop Shortcut - A^&D Thysia
cd /d "%~dp0"

echo ========================================================
echo    Creating Desktop Shortcut for A^&D Thysia System...
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo Tapos na! Pwede mo nang i-double click ang shortcut sa Desktop mo.
echo Press any key to exit.
pause >nul
