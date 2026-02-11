@echo off
chcp 65001 >nul
echo ========================================
echo 启动 Aim Stack 服务
echo ========================================
echo.

REM 检查 aim 是否安装
aim --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Aim 未安装
    echo.
    echo 请先安装 Aim:
    echo   pip install aim
    echo.
    pause
    exit /b 1
)

echo [信息] Aim 已安装
echo [启动] 正在启动 Aim Stack UI...
echo.
echo Aim UI 将在以下地址可用:
echo   http://localhost:43800
echo.
echo 按 Ctrl+C 停止服务
echo.

aim up --port 43800

pause




