@echo off

REM ============================================================================
REM Quant Crawler Web Launcher
REM ============================================================================

REM Configuration
set SCRIPT_DIR=%~dp0
set PYTHON_PATH=python
set SERVER_SCRIPT=server.py
set SERVER_PORT=9000
set BROWSER_URL=http://localhost:9000
set MAX_WAIT_SECONDS=30

REM ============================================================================
REM Main Entry Point
REM ============================================================================
:main

echo.
echo ============================================================================
echo                    Quant Crawler Web Launcher
echo ============================================================================
echo.

REM ============================================================================
REM Step 1: Check Python Environment
REM ============================================================================
echo [1/4] Checking Python environment...
%PYTHON_PATH% --version >nul 2>&1
if %ERRORLEVEL% equ 0 goto python_ok
    echo.
    echo ------------------------------------------------------------------------
    echo.
    echo   [ERROR] Python not found!
    echo.
    echo   Please ensure Python 3.6+ is installed.
    echo   Download: https://www.python.org/downloads/
    echo.
    echo ------------------------------------------------------------------------
    echo.
    pause
    exit /b 1
:python_ok
echo   [OK] Python environment check passed.
echo.

REM ============================================================================
REM Step 2: Check Server Script
REM ============================================================================
echo [2/4] Checking server script...
if exist "%SCRIPT_DIR%%SERVER_SCRIPT%" goto server_ok
    echo.
    echo ------------------------------------------------------------------------
    echo.
    echo   [ERROR] Server script not found.
    echo.
    echo   Please ensure %SERVER_SCRIPT% exists in:
    echo   %SCRIPT_DIR%
    echo.
    echo ------------------------------------------------------------------------
    echo.
    pause
    exit /b 1
:server_ok
echo   [OK] Server script check passed.
echo.

REM ============================================================================
REM Step 3: Start Backend Service
REM ============================================================================
echo [3/4] Starting backend service...

REM Change to script directory
cd /d "%SCRIPT_DIR%"

REM Start server in background
start "Quant Server" /B %PYTHON_PATH% "%SERVER_SCRIPT%" >nul 2>&1

REM Wait for server to start
echo   Waiting for service to start (max %MAX_WAIT_SECONDS% seconds)...
set WAIT_COUNT=0

:wait_loop
timeout /t 1 /nobreak >nul

REM Check if service started by testing port
netstat -an >nul 2>&1
if %ERRORLEVEL% equ 0 (
    netstat -an | findstr :%SERVER_PORT% >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo   [OK] Service started successfully.
        goto server_started
    )
)

set /a WAIT_COUNT+=1
if %WAIT_COUNT% geq %MAX_WAIT_SECONDS% (
    echo.
    echo ------------------------------------------------------------------------
    echo.
    echo   [ERROR] Service startup timeout.
    echo.
    echo   Possible causes:
    echo   - Port %SERVER_PORT% is already in use.
    echo   - Python script has errors.
    echo.
    echo   Suggestions:
    echo   1. Check port: netstat -ano
    echo   2. Run server.py manually to see detailed errors.
    echo.
    echo ------------------------------------------------------------------------
    echo.
    pause
    exit /b 1
)

goto wait_loop

:server_started
echo.

REM ============================================================================
REM Step 4: Open Browser
REM ============================================================================
echo [4/4] Opening browser...
echo.

REM Use PowerShell to open default browser
powershell -Command "Start-Process '%BROWSER_URL%'" >nul 2>&1

echo ------------------------------------------------------------------------
echo.
echo   [SUCCESS] Launch successful!
echo.
echo   Please access: %BROWSER_URL%
echo.
echo   Instructions:
echo   - Select single date or date range mode.
echo   - Click "Start Crawler" to run data collection.
echo   - Data will be saved to data/data_lake/{date}/
echo.
echo ------------------------------------------------------------------------
echo.
echo   Press any key to stop service and exit...
pause >nul

REM ============================================================================
REM Cleanup: Stop Server Process
REM ============================================================================
echo [Stopping] Closing service...

powershell -Command "Get-Process | Where-Object {$_.ProcessName -eq 'python' -and $_.MainWindowTitle -eq 'Quant Server'} | Stop-Process -Force" >nul 2>&1

echo   [OK] Service stopped.

exit /b 0
