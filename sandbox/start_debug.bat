@echo off
REM AquaTrade Debug Launcher
REM This script starts the server and allows AI to debug

cd /d "%~dp0"

echo ========================================
echo  AquaTrade Debug Mode
echo ========================================
echo.
echo  Starting services...
echo  AI can view logs and debug issues
echo.
echo ========================================

call .\venv\Scripts\activate.bat
honcho start
