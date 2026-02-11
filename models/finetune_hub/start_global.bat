@echo off
chcp 65001 >nul
echo ========================================
echo LLM Fine-tuning Hub 启动脚本（全局环境）
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)

echo [1/3] 检查 Node.js 依赖...
cd /d "%~dp0"
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
) else (
    echo 前端依赖已存在
)

echo [2/3] 启动后端 API 服务器（使用全局 Python 环境）...
start "LLM Fine-tuning Hub API" cmd.exe /k "cd /d ""%~dp0"" && python api_server.py"
timeout /t 3 >nul

echo [3/3] 启动前端开发服务器...
start "LLM Fine-tuning Hub Frontend" cmd.exe /k "cd /d ""%~dp0"" && npm run dev"

echo.
echo ========================================
echo ✓ 所有服务已启动：
echo   - 后端 API: http://localhost:5001
echo   - 前端应用: http://localhost:3000
echo   - 使用全局 Python 环境
echo ========================================
echo.
echo 提示: 请使用各窗口的 Ctrl+C 停止对应进程
echo.
timeout /t 2 >nul
start http://localhost:3000
pause




