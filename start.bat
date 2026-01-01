@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

:: ================= 配置 =================
set "USE_GRANIAN=true"
set "REDIS_HOME=D:\Redis-x64-5.0.14.1"

echo [1/5] 暴力清理残留进程 (防止端口占用)...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM granian.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

echo [2/5] 检查 Redis...
tasklist /FI "IMAGENAME eq redis-server.exe" 2>NUL | find /I /N "redis-server.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo    ✓ Redis 正常
) else (
    if exist "%REDIS_HOME%\redis-server.exe" (
        start "Redis" "%REDIS_HOME%\redis-server.exe"
        timeout /t 2 >nul
    ) else (
        echo [!] Redis 未找到，请手动启动
        pause
        exit /b 1
    )
)

echo [3/5] 启动 Worker...
start "Worker" cmd /k "set DB_BACKEND=lancedb&& set PARQUET_DIR=parquet_data&& python server\worker.py"

echo [4/5] 启动后端 (Granian)...
:: 核心修正：这里指向 run:app_asgi，而不是 server.granian_entry
:: 设置 Granian 日志级别为 info，减少 DEBUG 噪音（Scope received 等）
start "Backend (Granian)" cmd /k "set DB_BACKEND=lancedb&& set PARQUET_DIR=parquet_data&& set GRANIAN_LOG_LEVEL=info&& granian --interface asgi --host 0.0.0.0 --port 5000 --log-level info run:app_asgi"

echo [5/5] 启动前端...
set "MCP_DIR="
for /d %%D in ("%~dp0myapp") do set "MCP_DIR=%%~fD"
if defined MCP_DIR (
    start "Frontend" cmd /k "cd /d ""%MCP_DIR%"" && npm run dev"
)

echo.
echo [OK] 系统已重启。请等待浏览器自动打开。
timeout /t 5 >nul
start http://localhost:5173/
exit /b 0