@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

:: ========================================
::  AquaTrade Enhanced Startup Script
:: ========================================

:: ========================================
:: Configuration
:: ========================================
set "REDIS_HOME=D:\Redis-x64-5.0.14.1"
set "DOCKER_DESKTOP=C:\Program Files\Docker\Docker\resources\Docker Desktop.exe"
set "ENABLE_MCP=0"
set "ENABLE_TUSHARE_UPDATER=0"
set "AUTO_OPEN_BROWSER=1"

echo ========================================
echo  AquaTrade Startup Script
echo ========================================
echo.

:: ========================================
:: [1/7] Clean up old processes
:: ========================================
echo [1/7] Cleaning up old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
taskkill /F /IM granian.exe /T >nul 2>&1
taskkill /F /IM redis-server.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
echo       [OK] Process cleanup completed
echo.

:: ========================================
:: [2/7] Start QuestDB (Docker)
:: ========================================
echo [2/7] Starting QuestDB...

:: Check if Docker is running
docker ps >nul 2>&1
if %errorlevel% equ 0 (
    echo       Docker is already running
    goto docker_check_done
)

:: Docker not running, try to start Docker Desktop
echo       Docker is not running, attempting to start Docker Desktop...

if exist "%DOCKER_DESKTOP%" (
    start "" "%DOCKER_DESKTOP%"
    echo       [OK] Docker Desktop launched
    echo       Waiting for Docker to initialize (this may take 30-60 seconds)...
    
    :: Wait for Docker to be ready (max 60 seconds)
    set /a "docker_wait=0"
    :wait_docker_loop
    timeout /t 2 /nobreak >nul
    docker ps >nul 2>&1
    if %errorlevel% equ 0 (
        echo       [OK] Docker is now running
        goto docker_check_done
    )
    set /a "docker_wait+=2"
    if %docker_wait% lss 60 (
        echo       ...waiting (%docker_wait%s/60s)
        goto wait_docker_loop
    )
    
    :: Timeout reached
    echo.
    echo       [ERROR] ========================================
    echo       [ERROR] Docker failed to start within 60 seconds!
    echo       [ERROR] ========================================
    echo.
    echo       Please check:
    echo         1. Docker Desktop is installed correctly
    echo         2. Docker Desktop is not stuck in startup
    echo         3. WSL2 is properly configured
    echo.
    echo       Path: %DOCKER_DESKTOP%
    echo.
    echo       Press any key to exit...
    pause >nul
    exit /b 1
) else (
    echo       [ERROR] ========================================
    echo       [ERROR] Docker Desktop not found!
    echo       [ERROR] ========================================
    echo.
    echo       Expected path: %DOCKER_DESKTOP%
    echo.
    echo       Please:
    echo         1. Install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo         2. Or update DOCKER_DESKTOP path in this script
    echo.
    echo       Press any key to exit...
    pause >nul
    exit /b 1
)

:docker_check_done

:: Start QuestDB container
echo       Checking QuestDB container status...

:: Check if container is already running
docker ps | findstr questdb >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] QuestDB is already running
    goto questdb_done
)

:: Check if container exists but stopped
docker ps -a | findstr questdb >nul 2>&1
if %errorlevel% equ 0 (
    echo       QuestDB container exists but stopped, starting it...
    docker start questdb
    if %errorlevel% equ 0 (
        timeout /t 3 /nobreak >nul
        echo       [OK] QuestDB started
        goto questdb_done
    ) else (
        echo       [ERROR] Failed to start existing QuestDB container
        echo       You may need to remove and recreate it:
        echo         docker rm questdb
        echo       Then run this script again.
        echo.
        echo       Press any key to exit...
        pause >nul
        exit /b 1
    )
)

:: Container doesn't exist, create it
echo       Creating new QuestDB container...
docker run -d ^
  --name questdb ^
  -p 9000:9000 ^
  -p 9009:9009 ^
  -p 8812:8812 ^
  -v "%~dp0data\questdb:/var/lib/questdb" ^
  questdb/questdb

if %errorlevel% equ 0 (
    timeout /t 5 /nobreak >nul
    echo       [OK] QuestDB container created and running
) else (
    echo       [ERROR] Failed to create QuestDB container
    echo.
    echo       Possible reasons:
    echo       1. Ports 9000, 9009, 8812 are already in use by another application
    echo       2. Docker doesn't have permission to bind to these ports
    echo       3. The questdb/questdb image couldn't be pulled
    echo.
    echo       Current port usage:
    netstat -ano | findstr ":9000\|:9009\|:8812" 2>nul || echo       (No output - command failed)
    echo.
    echo       Press any key to exit...
    pause >nul
    exit /b 1
)

:questdb_done

echo.

:: ========================================
:: [3/7] Start Redis + Honcho (Parallel)
:: ========================================
echo [3/7] Starting Redis and Honcho services in parallel...

:: Start Redis in background
tasklist | findstr /I "redis-server.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Redis is already running
) else (
    echo       Starting Redis...
    if exist "%REDIS_HOME%\redis-server.exe" (
        start /B "Redis Server" "%REDIS_HOME%\redis-server.exe" >nul 2>&1
        echo       [OK] Redis started from: %REDIS_HOME%
    ) else (
        where redis-server >nul 2>&1
        if %errorlevel% equ 0 (
            start /B "Redis Server" redis-server >nul 2>&1
            echo       [OK] Redis started from system PATH
        ) else (
            echo       [ERROR] redis-server not found!
            echo       Please check REDIS_HOME path: %REDIS_HOME%
            echo       Or install Redis: https://github.com/microsoftarchive/redis/releases
            echo.
            echo       Press any key to exit...
            pause >nul
            exit /b 1
        )
    )
)

:: Start Honcho services immediately (parallel with Redis initialization)
echo       Starting Honcho services (Web, Worker, Frontend)...
start "AquaTrade Services (Honcho)" cmd.exe /k "chcp 65001 >nul && cd /d "%~dp0" && honcho start"

echo       [OK] All services launched in parallel
echo.

:: ========================================
:: [4/6] Optional: MCP Server
:: ========================================
if "%ENABLE_MCP%"=="1" (
    echo [4/6] Starting MCP Server...
    if exist "%~dp0myapp" (
        start "Aquatrade MCP Server" cmd.exe /k "cd /d "%~dp0myapp" && set AQUATRADE_API=http://127.0.0.1:5000 && npx -y tsx src/server.ts"
        echo       [OK] MCP Server started
        timeout /t 2 /nobreak >nul
    ) else (
        echo       [WARNING] myapp directory not found
    )
) else (
    echo [4/6] MCP Server disabled (set ENABLE_MCP=1 to enable)
)
echo.

:: ========================================
:: [5/6] Optional: Tushare Updater
:: ========================================
if "%ENABLE_TUSHARE_UPDATER%"=="1" (
    echo [5/6] Starting Tushare data updater...
    start "Aquatrade Tushare Updater" /B cmd.exe /C "cd /d "%~dp0" && set ENABLE_TUSHARE_UPDATER=1 && python -m database.tushare_updater"
    echo       [OK] Tushare updater started in background
) else (
    echo [5/6] Tushare updater disabled (set ENABLE_TUSHARE_UPDATER=1 to enable)
)
echo.

:: ========================================
:: [6/6] Open Browser
:: ========================================
if "%AUTO_OPEN_BROWSER%"=="1" (
    echo [6/6] Opening browser...
    timeout /t 2 /nobreak >nul
    start http://localhost:5173/
    echo       [OK] Browser opened
) else (
    echo [6/6] Auto-open browser disabled
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
echo  Dependencies:
echo   - Redis:         localhost:6379
echo   - Docker:        Check status above
echo.
if "%ENABLE_MCP%"=="1" echo   - MCP Server:    Running
if "%ENABLE_TUSHARE_UPDATER%"=="1" echo   - Tushare:       Running in background
echo.
echo ========================================
echo  Configuration:
echo   - REDIS_HOME:              %REDIS_HOME%
echo   - DOCKER_DESKTOP:          %DOCKER_DESKTOP%
echo   - ENABLE_MCP:              %ENABLE_MCP%
echo   - ENABLE_TUSHARE_UPDATER:  %ENABLE_TUSHARE_UPDATER%
echo   - AUTO_OPEN_BROWSER:       %AUTO_OPEN_BROWSER%
echo ========================================
echo.
echo  To stop: Close the Honcho window or press Ctrl+C
echo.
endlocal
exit /b 0
