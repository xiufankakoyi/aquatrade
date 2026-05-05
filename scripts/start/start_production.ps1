# ========================================
#  AquaTrade Production Mode Launcher
#  生产模式：ArcticDB + Polars + 真实后端
#  用途：实际交易、数据分析、生产环境
# ========================================

param(
    [string]$REDIS_HOME = "C:\Program Files\Redis",
    [int]$AUTO_OPEN_BROWSER = 1,
    [int]$ENABLE_TUSHARE_UPDATER = 0
)

$ErrorActionPreference = "Continue"

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:DEFAULT_DATA_SOURCE = "arctic"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

Write-Host "========================================"
Write-Host " AquaTrade Production Mode"
Write-Host "========================================"
Write-Host ""
Write-Host "  Mode: Full Stack (ArcticDB + Polars)"
Write-Host "  Backend: Enabled"
Write-Host "  Data: Real (ArcticDB + Polars)"
Write-Host ""

# ========================================
# [1/6] Clean up old processes
# ========================================
Write-Host "[1/6] Cleaning up..."
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "granian" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Host "      [OK]"
Write-Host ""

# ========================================
# [2/6] Check ArcticDB Data Directory
# ========================================
Write-Host "[2/6] Checking ArcticDB..."

$arcticDataDir = Join-Path $repoRoot "data\arctic_db"
if (-not (Test-Path $arcticDataDir)) {
    New-Item -ItemType Directory -Path $arcticDataDir -Force | Out-Null
    Write-Host "      [OK] Created ArcticDB directory"
} else {
    Write-Host "      [OK] ArcticDB directory exists"
}

# 检查是否有数据 (ArcticDB LMDB 格式使用 _arctic_cfg 目录)
$arcticMetaDir = Join-Path $arcticDataDir "_arctic_cfg"
if (Test-Path $arcticMetaDir) {
    Write-Host "      [OK] ArcticDB has data"
} else {
    Write-Host "      [WARN] ArcticDB is empty, run data migration first:"
    Write-Host "             python sandbox/full_migration_all_stocks.py"
}
Write-Host ""

# ========================================
# [3/6] Start Redis
# ========================================
Write-Host "[3/6] Starting Redis..."

$redisProcess = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
if (-not $redisProcess) {
    $redisExe = Join-Path $REDIS_HOME "redis-server.exe"
    if (Test-Path $redisExe) {
        Start-Process -FilePath $redisExe -WindowStyle Hidden
    } elseif (Get-Command "redis-server" -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "redis-server" -WindowStyle Hidden
    }
}
Write-Host "      [OK]"
Write-Host ""

# ========================================
# [4/6] Parallel: Backend + Frontend
# ========================================
Write-Host "[4/6] Starting services in parallel..."

$venvActivate = Join-Path $repoRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

# 启动后端 (禁用 Mock)
$backendCmd = @"
Set-Location '$repoRoot'
`$env:PYTHONIOENCODING='utf-8'
`$env:DEFAULT_DATA_SOURCE='arctic'
honcho start web worker
"@

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal

# 启动前端 (禁用 Mock)
$myappPath = Join-Path $repoRoot "myapp"
if (Test-Path $myappPath) {
    $frontendCmd = @"
Set-Location '$myappPath'
`$env:VITE_USE_MOCK='false'
npm run dev
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
}

Write-Host "      [OK] Backend & Frontend starting"
Write-Host ""

# ========================================
# [5/6] Open browser
# ========================================
Write-Host "[5/6] Opening browser..."

if ($AUTO_OPEN_BROWSER -eq 1) {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5173/"
    Write-Host "      [OK] Browser opened"
}
Write-Host ""

# ========================================
# [6/6] Optional: Tushare Updater
# ========================================
if ($ENABLE_TUSHARE_UPDATER -eq 1) {
    Write-Host "[6/6] Starting Tushare Updater..."
    $updaterCmd = "Set-Location '$repoRoot'; python -c 'from data_svc.tushare_updater import start_scheduler; start_scheduler()'"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $updaterCmd -WindowStyle Minimized
    Write-Host "      [OK]"
} else {
    Write-Host "[6/6] Tushare Updater disabled"
}
Write-Host ""

# ========================================
# Done
# ========================================
Write-Host "========================================"
Write-Host " Production Mode Started!"
Write-Host "========================================"
Write-Host ""
Write-Host "  - Frontend:     http://localhost:5173"
Write-Host "  - Backend:      http://localhost:5000"
Write-Host "  - Redis:        localhost:6379"
Write-Host "  - Data Source:  ArcticDB + Polars"
Write-Host "  - ArcticDB:     $arcticDataDir"
Write-Host ""
Write-Host "  [INFO] Using ArcticDB (high-performance storage)"
Write-Host "  [INFO] Vectorized execution: ENABLED"
Write-Host "  [INFO] Mock mode: DISABLED"
Write-Host ""
Write-Host " Features:"
Write-Host "  - Real K-line data from ArcticDB"
Write-Host "  - Expression analysis with Polars"
Write-Host "  - Real-time backtesting"
Write-Host "  - Live data updates"
Write-Host ""
Write-Host " To stop: Close service windows"
Write-Host "========================================"
Write-Host ""

# 可选：显示数据迁移提示
if (-not (Test-Path $arcticMetaDir)) {
    Write-Host "========================================"
    Write-Host " DATA MIGRATION REQUIRED"
    Write-Host "========================================"
    Write-Host ""
    Write-Host " ArcticDB is empty. Please migrate data:"
    Write-Host ""
    Write-Host "   python sandbox/full_migration_all_stocks.py"
    Write-Host ""
    Write-Host "========================================"
    Write-Host ""
}
