# ========================================
#  AquaTrade LanceDB Startup Script
#  Data Backend: LanceDB + Polars
#  Auto Start: Backend + Frontend + Browser
# ========================================

param(
    [string]$REDIS_HOME = "C:\Program Files\Redis",
    [int]$AUTO_OPEN_BROWSER = 1,
    [int]$ENABLE_MCP = 0,
    [int]$ENABLE_TUSHARE_UPDATER = 0
)

$ErrorActionPreference = "Continue"

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:DB_BACKEND = "lancedb"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

Write-Host "========================================"
Write-Host " AquaTrade LanceDB Mode"
Write-Host "========================================"
Write-Host ""
Write-Host "  Data Backend: LanceDB + Polars"
Write-Host "  Database:     data/lancedb"
Write-Host ""

# ========================================
# [1/5] Cleanup old processes
# ========================================
Write-Host "[1/5] Cleanup old processes..."
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "granian" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Host "      [OK]"
Write-Host ""

# ========================================
# [2/5] Check LanceDB data directory
# ========================================
Write-Host "[2/5] Checking LanceDB data..."

$lancedbDir = Join-Path $repoRoot "data\lancedb"
if (-not (Test-Path $lancedbDir)) {
    New-Item -ItemType Directory -Path $lancedbDir -Force | Out-Null
    Write-Host "      [WARN] LanceDB directory created, please import data first"
} else {
    $tables = Get-ChildItem $lancedbDir -Directory -ErrorAction SilentlyContinue
    if ($tables) {
        Write-Host "      [OK] LanceDB tables:"
        foreach ($t in $tables) {
            Write-Host "         - $($t.Name)"
        }
    } else {
        Write-Host "      [WARN] LanceDB directory is empty"
    }
}
Write-Host ""

# ========================================
# [3/5] Start Redis
# ========================================
Write-Host "[3/5] Starting Redis..."

$redisProcess = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
if (-not $redisProcess) {
    $redisExe = Join-Path $REDIS_HOME "redis-server.exe"
    if (Test-Path $redisExe) {
        Start-Process -FilePath $redisExe -WindowStyle Hidden
        Write-Host "      [OK] Redis started"
    } elseif (Get-Command "redis-server" -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "redis-server" -WindowStyle Hidden
        Write-Host "      [OK] Redis started"
    } else {
        Write-Host "      [SKIP] Redis not installed, skipping"
    }
} else {
    Write-Host "      [OK] Redis is already running"
}
Write-Host ""

# ========================================
# [4/5] Start Backend + Frontend
# ========================================
Write-Host "[4/5] Starting backend service..."

$venvActivate = Join-Path $repoRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

$backendCmd = @"
Set-Location '$repoRoot'
`$env:PYTHONIOENCODING='utf-8'
`$env:DB_BACKEND='lancedb'
honcho start web worker
"@

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Minimized
Write-Host "      [OK] Backend starting..."

Start-Sleep -Seconds 2

Write-Host "[4/5] Starting frontend service..."

$myappPath = Join-Path $repoRoot "myapp"
if (Test-Path $myappPath) {
    $frontendCmd = @"
Set-Location '$myappPath'
npm run dev
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Minimized
    Write-Host "      [OK] Frontend starting..."
}
Write-Host ""

# ========================================
# [5/5] Open browser
# ========================================
Write-Host "[5/5] Opening browser..."

if ($AUTO_OPEN_BROWSER -eq 1) {
    Start-Sleep -Seconds 3
    $launcherPath = Join-Path $myappPath "public\launcher.html"
    if (Test-Path $launcherPath) {
        Start-Process $launcherPath
        Write-Host "      [OK] Launcher page opened"
    } else {
        Start-Process "http://localhost:5173/"
        Write-Host "      [OK] Browser opened http://localhost:5173"
    }
}
Write-Host ""

# ========================================
# [Optional] Start MCP Server
# ========================================
if ($ENABLE_MCP -eq 1) {
    Write-Host "[Optional] Starting MCP Server..."
    if (Test-Path $myappPath) {
        $mcpCmd = "Set-Location '$myappPath'; `$env:AQUATRADE_API='http://127.0.0.1:5000'; npx -y tsx src/server.ts"
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $mcpCmd -WindowStyle Minimized
        Write-Host "      [OK]"
    }
}

# ========================================
# [Optional] Start Tushare Updater
# ========================================
if ($ENABLE_TUSHARE_UPDATER -eq 1) {
    Write-Host "[Optional] Starting Tushare Updater..."
    $updaterCmd = "Set-Location '$repoRoot'; python -c 'from data_svc.tushare_updater import start_scheduler; start_scheduler()'"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $updaterCmd -WindowStyle Minimized
    Write-Host "      [OK]"
}

# ========================================
# Done
# ========================================
Write-Host "========================================"
Write-Host " AquaTrade LanceDB Started!"
Write-Host "========================================"
Write-Host ""
Write-Host "  Frontend:  http://localhost:5173"
Write-Host "  Backend:   http://localhost:5000"
Write-Host "  Redis:    localhost:6379"
Write-Host ""
Write-Host "  Data:     LanceDB (data/lancedb)"
Write-Host "  Engine:   Polars + Numba"
Write-Host ""
Write-Host "  To stop:  Close all service windows"
Write-Host "========================================"
Write-Host ""
