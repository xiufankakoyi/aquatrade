# ========================================
#  AquaTrade Mock Mode Launcher
#  Mock模式：前端模拟数据，无需后端服务
#  用途：快速预览界面、演示、开发测试
# ========================================

param(
    [int]$AUTO_OPEN_BROWSER = 1
)

$ErrorActionPreference = "Continue"

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

Write-Host "========================================"
Write-Host " AquaTrade Mock Mode"
Write-Host "========================================"
Write-Host ""
Write-Host "  Mode: Frontend Only (Mock Data)"
Write-Host "  Backend: Not Required"
Write-Host "  Data: Simulated"
Write-Host ""

# ========================================
# [1/3] Clean up old processes
# ========================================
Write-Host "[1/3] Cleaning up..."
Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Write-Host "      [OK]"
Write-Host ""

# ========================================
# [2/3] Start Frontend Only
# ========================================
Write-Host "[2/3] Starting Frontend with Mock data..."

$myappPath = Join-Path $repoRoot "myapp"
if (Test-Path $myappPath) {
    $frontendCmd = @"
Set-Location '$myappPath'
`$env:VITE_USE_MOCK='true'
npm run dev
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    Write-Host "      [OK] Frontend starting with MOCK data"
} else {
    Write-Host "      [ERROR] Frontend directory not found"
    exit 1
}
Write-Host ""

# ========================================
# [3/3] Open browser
# ========================================
Write-Host "[3/3] Opening browser..."

if ($AUTO_OPEN_BROWSER -eq 1) {
    Start-Process "http://localhost:5173/"
    Write-Host "      [OK] Browser opened"
}
Write-Host ""

# ========================================
# Done
# ========================================
Write-Host "========================================"
Write-Host " Mock Mode Started!"
Write-Host "========================================"
Write-Host ""
Write-Host "  - Frontend:     http://localhost:5173"
Write-Host "  - Mode:         MOCK (No backend needed)"
Write-Host "  - Data:         Simulated"
Write-Host ""
Write-Host " Features:"
Write-Host "  - K-line charts with random data"
Write-Host "  - Strategy list (mock)"
Write-Host "  - Backtest results (mock)"
Write-Host "  - Sentiment data (mock)"
Write-Host ""
Write-Host " To stop: Close the frontend window"
Write-Host "========================================"
Write-Host ""
