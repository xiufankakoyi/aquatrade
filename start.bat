@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start\start_lancedb.ps1" %*
