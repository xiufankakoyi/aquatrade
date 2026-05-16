@echo off
chcp 65001 >nul
echo ========================================
echo  AquaTrade Mock Mode Launcher
echo ========================================
echo.
echo  Mode: Frontend Only (Mock Data)
echo  Backend: Not Required
echo  Data: Simulated
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0start_mock.ps1"

pause
