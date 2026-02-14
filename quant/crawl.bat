@echo off
REM ============================================================================
REM Quant Crawler Runner - 直接运行爬虫
REM ============================================================================

REM 切换到脚本目录
cd /d "%~dp0"

REM 运行爬虫
python main_launcher.py %1

REM 返回退出码
exit /b %ERRORLEVEL%
