:: 环境变量配置
set DB_BACKEND=lancedb
set PARQUET_DIR=parquet_data
set GRANIAN_LOG_LEVEL=info

:loop
cls
echo ========================================================
echo [模式] 手动挡 (Manual Mode)
echo [状态] 后端正在运行...
echo [操作] 改完代码后，请按 Ctrl+C，然后输入 N 来重启！
echo ========================================================
echo.

:: 启动命令 (去掉了所有 --reload 参数)
granian --interface asgi --host 0.0.0.0 --port 5000 --log-level info run:app_asgi

:: 当你按 Ctrl+C 杀掉 Granian 后，会执行下面的代码
echo.
echo ========================================================
echo [INFO] 后端已停止。
echo [提示] 正在重新启动... (如果不重启请直接关闭窗口)
echo ========================================================
timeout /t 1 >nul
goto loop