@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

::Config: Redis 安装路径
set "REDIS_HOME=D:\Redis-x64-5.0.14.1"

echo [1/8] 检查 Redis 服务状态...
:: 1. 首先检查进程是否已经在运行
tasklist /FI "IMAGENAME eq redis-server.exe" 2>NUL | find /I /N "redis-server.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo    ✓ Redis 服务已在运行。
) else (
    echo    Redis 未启动，正在尝试启动...
    if exist "%REDIS_HOME%\redis-server.exe" (
        start "Redis Server" "%REDIS_HOME%\redis-server.exe"
        echo    Redis 已启动。
        :: 等待 3 秒让 Redis 完成初始化
        timeout /t 3 >nul
    ) else (
        echo [!] 严重错误: 未找到 Redis，路径无效: %REDIS_HOME%
        echo [!] 请检查路径是否正确，或手动启动 Redis。
        pause
        exit /b 1
    )
)

:: 2. 二次确认连接 (双重保险)
python -c "import redis; r=redis.from_url('redis://localhost:6379/0'); r.ping(); print('   ✓ Redis 端口连接测试通过')" 2>nul
if errorlevel 1 (
    echo [!] 警告: Redis 进程已启动但无法连接，尝试等待 2 秒...
    timeout /t 2 >nul
)

echo [2/8] 正在启动 Worker 进程 (worker.py)...
start "Aquatrade Worker (Redis Consumer)" cmd.exe /k "cd /d ""%~dp0"" && set "DB_BACKEND=duckdb" && set "PARQUET_DIR=parquet_data" && python worker.py"

echo [3/8] 等待 Worker 进程初始化...
timeout /t 2 >nul

echo [4/8] 正在启动量化回测后端 (python app.py)...
start "Aquatrade Backend (Flask)" cmd.exe /k "cd /d ""%~dp0"" && set "DB_BACKEND=duckdb" && set "PARQUET_DIR=parquet_data" && python app.py"

echo [5/8] 等待后端服务准备就绪...
timeout /t 5 >nul

echo [6/8] 正在启动 MCP 服务器...
set "MCP_DIR="
for /d %%D in ("%~dp0myapp") do (
    set "MCP_DIR=%%~fD"
)
if defined MCP_DIR (
    start "Aquatrade MCP Server" cmd.exe /k "cd /d ""%MCP_DIR%"" && set AQUATRADE_API=http://127.0.0.1:5000 && npx -y tsx src/server.ts"
    echo    ✓ MCP 服务器已启动
) else (
    echo [!] 未找到 myapp 目录，跳过 MCP 服务器启动
)

echo [7/8] 等待 MCP 服务器初始化...
timeout /t 3 >nul

echo [8/8] 正在定位前端目录 (myapp)...
set "FRONT_DIR="
for /d %%D in ("%~dp0myapp") do (
    set "FRONT_DIR=%%~fD"
)
if not defined FRONT_DIR (
    echo [!] 未找到 myapp 前端目录，请确认文件夹是否存在。
    pause
    exit /b 1
)

echo [附加] 正在启动前端服务器 (npm run dev)...
start "Aquatrade Frontend (Vite)" cmd.exe /k "cd /d ""%FRONT_DIR%"" && npm run dev"

echo [附加] 正在后台启动 Tushare 数据增量更新任务...
start "Aquatrade Tushare Updater" /B cmd.exe /C "cd /d ""%~dp0"" && set ENABLE_TUSHARE_UPDATER=1 && python -m database.tushare_updater"

echo.
echo [完成] 正在打开浏览器窗口...
timeout /t 2 >nul
start http://localhost:5173/

echo.
echo ========================================
echo ✓ 所有服务已启动：
echo   - Redis 服务器: localhost:6379 (路径: %REDIS_HOME%)
echo   - Worker 进程: 已启动 (监听 Redis 队列)
echo   - 后端服务: http://localhost:5000
echo   - 前端服务: http://localhost:5173
echo   - MCP 服务器: 已启动 (stdio)
echo   - 数据更新任务: 已在后台启动
echo ========================================
echo.
echo 提示: 请使用各窗口的 Ctrl+C 停止对应进程
echo.
echo 架构说明:
echo   - Web Server (app.py) 推送任务 -> Redis Queue
echo   - Worker (worker.py) 处理任务 -> Redis Pub/Sub 推送进度
echo.
endlocal
exit /b 0