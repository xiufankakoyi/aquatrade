@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -Command "& {.\venv\Scripts\Activate.ps1; honcho start}"
pause
