@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo [1/6] 正在启动量化回测后端 (python app.py)...
start "Aquatrade Backend (Flask)" cmd.exe /k "cd /d ""%~dp0"" && set "DB_BACKEND=duckdb" && set "PARQUET_DIR=parquet_data" && python app.py"

echo [2/6] 等待后端服务准备就绪...
timeout /t 5 >nul

echo [3/6] 正在启动 MCP 服务器...
set "MCP_DIR="
for /d %%D in ("%~dp0myapp") do (
    set "MCP_DIR=%%~fD"
)
if defined MCP_DIR (
    start "Aquatrade MCP Server" cmd.exe /k "cd /d ""%MCP_DIR%"" && set AQUATRADE_API=http://127.0.0.1:5000 && npx -y tsx src/server.ts"
    echo     MCP 服务器已启动
) else (
    echo [!] 未找到 myapp 目录，跳过 MCP 服务器启动
)

echo [4/6] 等待 MCP 服务器初始化...
timeout /t 3 >nul

echo [5/6] 正在定位前端目录 (myapp)...
set "FRONT_DIR="
for /d %%D in ("%~dp0myapp") do (
    set "FRONT_DIR=%%~fD"
)
if not defined FRONT_DIR (
    echo [!] 未找到 myapp 前端目录，请确认文件夹是否存在。
    pause
    exit /b 1
)

echo [6/6] 正在启动前端服务器 (npm run dev)...
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
echo   - 后端服务: http://localhost:5000
echo   - 前端服务: http://localhost:5173
echo   - MCP 服务器: 已启动 (stdio)
echo   - 数据更新任务: 已在后台启动
echo ========================================
echo.
echo 提示: 请使用各窗口的 Ctrl+C 停止对应进程
echo.
endlocal
exit /b 0