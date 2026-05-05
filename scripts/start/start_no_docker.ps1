# ========================================
#  AquaTrade No-Docker Startup Script (PowerShell)
#  极速启动模式：ArcticDB + Polars + Redis + 并行启动
#  目标：1.5秒内用户看到首屏
# ========================================

param(
    [string]$REDIS_HOME = "C:\Program Files\Redis",
    [int]$ENABLE_MCP = 0,
    [int]$ENABLE_TUSHARE_UPDATER = 0,
    [int]$AUTO_OPEN_BROWSER = 1,
    [string]$DB_BACKEND = "arcticdb"
)

$ErrorActionPreference = "Continue"

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:DB_BACKEND = $DB_BACKEND

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

Write-Host "========================================"
Write-Host " AquaTrade Quick Start"
Write-Host " Mode: ArcticDB + Polars + Parallel + Static Launcher"
Write-Host "========================================"
Write-Host ""

# ========================================
# [1/5] Clean up old processes (fast)
# ========================================
Write-Host "[1/5] Cleaning up..."
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "granian" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Host "      [OK]"
Write-Host ""

# ========================================
# [2/5] Start Redis (hidden window)
# ========================================
Write-Host "[2/5] Starting Redis..."

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
# [3/5] Parallel: Backend + Frontend
# ========================================
Write-Host "[3/5] Starting services in parallel..."

$venvActivate = Join-Path $repoRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

$backendCmd = @"
Set-Location '$repoRoot'
`$env:PYTHONIOENCODING='utf-8'
`$env:DB_BACKEND='$($env:DB_BACKEND)'
honcho start web worker
"@

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Minimized

$myappPath = Join-Path $repoRoot "myapp"
if (Test-Path $myappPath) {
    $frontendCmd = @"
Set-Location '$myappPath'
npm run dev
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Minimized
}

Write-Host "      [OK] Backend & Frontend starting"
Write-Host ""

# ========================================
# [4/5] Open browser immediately (static launcher)
# ========================================
Write-Host "[4/5] Opening browser..."

if ($AUTO_OPEN_BROWSER -eq 1) {
    $launcherPath = Join-Path $myappPath "public\launcher.html"
    if (Test-Path $launcherPath) {
        Start-Process $launcherPath
        Write-Host "      [OK] Launcher opened (static HTML)"
    } else {
        Start-Process "http://localhost:5173/"
        Write-Host "      [OK] Browser opened"
    }
}
Write-Host ""

# ========================================
# [6/6] Optional: MCP Server
# ========================================
if ($ENABLE_MCP -eq 1) {
    Write-Host "[5/5] Starting MCP Server..."
    if (Test-Path $myappPath) {
        $mcpCmd = "Set-Location '$myappPath'; `$env:AQUATRADE_API='http://127.0.0.1:5000'; npx -y tsx src/server.ts"
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $mcpCmd -WindowStyle Minimized
        Write-Host "      [OK]"
    }
} else {
    Write-Host "[5/5] MCP Server disabled"
}
Write-Host ""

# ========================================
# Done
# ========================================
Write-Host "========================================"
Write-Host " Services Started!"
Write-Host "========================================"
Write-Host ""
Write-Host "  - Frontend:  http://localhost:5173"
Write-Host "  - Backend:   http://localhost:5000"
Write-Host "  - Redis:     localhost:6379"
Write-Host "  - DB Backend: $($env:DB_BACKEND) (ArcticDB + Polars)"
Write-Host ""
Write-Host " The launcher page will auto-redirect"
Write-Host " when Vite is ready."
Write-Host ""
Write-Host " To stop: Close service windows"
Write-Host "========================================"
Write-Host ""
