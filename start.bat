@echo off
chcp 65001 >nul
title AquaTrade Launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start\start_aquatrade.ps1" %*
if errorlevel 1 (
    echo.
    echo AquaTrade startup failed. Check the error above.
    pause
)
