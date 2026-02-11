@echo off
REM QuestDB 一键启动脚本
REM 使用 Docker 启动 QuestDB 服务

echo ========================================
echo  QuestDB 启动脚本
echo ========================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Docker，请先安装 Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo [1/3] 检查现有容器...
docker ps -a | findstr questdb >nul 2>&1
if %errorlevel% equ 0 (
    echo       已存在 questdb 容器，正在启动...
    docker start questdb
) else (
    echo       创建新容器...
    docker run -d ^
      --name questdb ^
      -p 9000:9000 ^
      -p 9009:9009 ^
      -p 8812:8812 ^
      -v "%~dp0data\questdb:/var/lib/questdb" ^
      questdb/questdb
)

echo.
echo [2/3] 等待服务启动...
timeout /t 5 /nobreak >nul

echo.
echo [3/3] 检查健康状态...
curl -s http://localhost:9000/exec?query=SELECT+1 >nul 2>&1
if %errorlevel% equ 0 (
    echo       ✓ QuestDB 运行正常
    echo.
    echo ========================================
    echo  启动成功！
    echo ========================================
    echo.
    echo  Web UI: http://localhost:9000
    echo  ILP 端口: 9009
    echo  PostgreSQL 端口: 8812
    echo.
    echo  数据目录: %~dp0data\questdb
    echo ========================================
) else (
    echo       ✗ 服务启动失败，请查看 Docker 日志
    docker logs questdb
)

echo.
pause
