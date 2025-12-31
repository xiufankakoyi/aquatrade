@echo off
chcp 65001 >nul
echo ========================================
echo LLM Fine-tuning Hub 启动脚本
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

echo [1/4] 检查 Python 依赖...
cd /d "%~dp0"

REM 检查是否使用全局环境
set USE_GLOBAL_ENV=%1
if "%USE_GLOBAL_ENV%"=="--global" (
    echo 使用全局 Python 环境...
    set PYTHON_ENV=global
) else (
    echo 使用虚拟环境...
    if not exist "venv" (
        echo 创建虚拟环境...
        python -m venv venv
    )
    call venv\Scripts\activate.bat
    set PYTHON_ENV=venv
)

REM 只在虚拟环境中安装依赖
if "%PYTHON_ENV%"=="venv" (
    pip install -q -r requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo [警告] 部分依赖安装失败，继续运行...
    )
) else (
    echo [提示] 使用全局环境，请确保已安装所需依赖
    echo [提示] 如需安装依赖: pip install -r requirements.txt
)

echo [2/4] 检查 Node.js 依赖...
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
) else (
    echo 前端依赖已存在
)

echo [3/4] 启动后端 API 服务器...
if "%PYTHON_ENV%"=="venv" (
    start "LLM Fine-tuning Hub API" cmd.exe /k "cd /d ""%~dp0"" && call venv\Scripts\activate.bat && python api_server.py"
) else (
    start "LLM Fine-tuning Hub API" cmd.exe /k "cd /d ""%~dp0"" && python api_server.py"
)
timeout /t 3 >nul

echo [4/4] 启动前端开发服务器...
start "LLM Fine-tuning Hub Frontend" cmd.exe /k "cd /d ""%~dp0"" && npm run dev"

echo.
echo ========================================
echo ✓ 所有服务已启动：
echo   - 后端 API: http://localhost:5001
echo   - 前端应用: http://localhost:3000
echo ========================================
echo.
echo 提示: 请使用各窗口的 Ctrl+C 停止对应进程
echo.
timeout /t 2 >nul
start http://localhost:3000
pause

