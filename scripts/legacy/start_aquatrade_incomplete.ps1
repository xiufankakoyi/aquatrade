# ========================================
#  AquaTrade Trading Platform
#  One-Click Start Script (PowerShell)
#  Real Backend + Frontend + Redis
# ========================================

param(
    [string]$REDIS_HOME = "C:\Program Files\Redis",
    [int]$AUTO_OPEN_BROWSER = 1,
    [string]$DB_BACKEND = "questdb"
)

$ErrorActionPreference = "Continue"

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:DB_BACKEND = $DB_BACKEND

# 获取脚本所在目录 - 使用当前目录作为基准
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

Write-Host "========================================"
Write-Host " AquaTrade Trading
