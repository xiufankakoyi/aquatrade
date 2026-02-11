@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

:: ========================================
::  AquaTrade No-Docker Startup Script
::  使用 DuckDB 作为数据库后端，无需 Docker
:: ========================================

:: ========================================
:: Configuration
:: ========================================
set "REDIS_HOME=D:\Redis-x64-5.0.14.1"
set "ENABLE_MCP=0"
set "ENABLE_TUSHARE_UPDATER=0"
set "AUTO_OPEN_BROWSER=1"

:: 强制使用 DuckDB 后端
set "DB_BACKEND=duckdb"

echo ========================================
echo  AquaTrade No-Docker Startup Script
echo  Database Backend: DuckDB (Parquet)
echo ========================================
echo.

:: ========================================
:: [1/5] Clean up old processes
:: ========================================
echo [1/5] Cleaning up old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
taskkill /F /IM granian.exe /T >nul 2>&1
taskkill /F /IM redis-server.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
echo       [OK] Process cleanup completed
echo.

:: ========================================
:: [2/5] Check DuckDB data files
:: ========================================
echo [2/5] Checking DuckDB data files...
if exist "%~dp0data\parquet_data\base_daily_hot.parquet" (
    echo       [OK] Hot data files found
) else (
    echo       [WARNING] Hot data files not found in data\parquet_data\
    echo       You may need to run data import first
)
echo.

:: ========================================
:: [3/5] Start Redis
:: ========================================
echo [3/5] Starting Redis...

tasklist | findstr /I "redis-server.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Redis is already running
    goto redis_verify
)

echo       Redis is not running, attempting to start...

if exist "%REDIS_HOME%\redis-server.exe" (
    start "Redis Server" "%REDIS_HOME%\redis-server.exe"
    echo       [OK] Redis started from: %REDIS_HOME%
    timeout /t 3 /nobreak >nul
    goto redis_verify
)

where redis-server >nul 2>&1
if %errorlevel% equ 0 (
    start "Redis Server" redis-server
    echo       [OK] Redis started from system PATH
    timeout /t 3 /nobreak >nul
    goto redis_verify
)

echo       [ERROR] redis-server not found!
echo       Please check REDIS_HOME path: %REDIS_HOME%
echo       Or install Redis: https://github.com/microsoftarchive/redis/releases
echo.
echo       Press any key to continue without Redis (Worker will fail)...
pause >nul
goto redis_done

:redis_verify
python -c "import redis; r=redis.from_url('redis://localhost:6379/0'); r.ping(); print('       [OK] Redis connection verified')" 2>nul
if errorlevel 1 (
    echo       [WARNING] Redis connection test failed, waiting...
    timeout /t 2 /nobreak >nul
)

:redis_done
echo.

:: ========================================
:: [4/5] Start Honcho services
:: ========================================
echo [4/5] Starting main services via Honcho...
echo       This will start: Web (5000), Worker, Frontend (5173)
echo       Database Backend: DuckDB (Parquet files)
echo.

start "AquaTrade Services (Honcho)" cmd.exe /k "chcp 65001 >nul && cd /d "%~dp0" && set DB_BACKEND=duckdb && honcho start"

echo       Waiting for services to initialize...
timeout /t 5 /nobreak >nul
echo.

:: ========================================
:: [5/5] Optional: MCP Server
:: ========================================
if "%ENABLE_MCP%"=="1" (
    echo [5/5] Starting MCP Server...
    if exist "%~dp0myapp" (
        start "Aquatrade MCP Server" cmd.exe /k "cd /d "%~dp0myapp" && set AQUATRADE_API=http://127.0.0.1:5000 && npx -y tsx src/server.ts"
        echo       [OK] MCP Server started
        timeout /t 2 /nobreak >nul
    ) else (
        echo       [WARNING] myapp directory not found
    )
) else (
    echo [5/5] MCP Server disabled (set ENABLE_MCP=1 to enable)
)
echo.

:: ========================================
:: [6/5] Open Browser
:: ========================================
if "%AUTO_OPEN_BROWSER%"=="1" (
    echo [6/5] Opening browser...
    timeout /t 2 /nobreak >nul
    start http://localhost:5173/
    echo       [OK] Browser opened
) else (
    echo [6/5] Auto-open browser disabled
)
echo.

:: ========================================
:: Startup Complete
:: ========================================
echo ========================================
echo  All Services Started Successfully!
echo ========================================
echo.
echo  Core Services (via Honcho):
echo   - Web Server:    http://localhost:5000
echo   - Worker:        Running (Redis consumer)
echo   - Frontend:      http://localhost:5173
echo.
echo  Database Backend:
echo   - DuckDB + Parquet (No Docker required!)
echo   - Data location: data\parquet_data\
echo.
echo  Dependencies:
echo   - Redis:         localhost:6379
echo   - Docker:        Not required
echo.
if "%ENABLE_MCP%"=="1" echo   - MCP Server:    Running
if "%ENABLE_TUSHARE_UPDATER%"=="1" echo   - Tushare:       Running in background
echo.
echo ========================================
echo  Configuration:
echo   - REDIS_HOME:              %REDIS_HOME%
echo   - DB_BACKEND:              duckdb (forced)
echo   - ENABLE_MCP:              %ENABLE_MCP%
echo   - ENABLE_TUSHARE_UPDATER:  %ENABLE_TUSHARE_UPDATER%
echo   - AUTO_OPEN_BROWSER:       %AUTO_OPEN_BROWSER%
echo ========================================
echo.
echo  To stop: Close the Honcho window or press Ctrl+C
echo.
endlocal
exit /b 0
