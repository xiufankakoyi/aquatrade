param(
    [switch]$NoBrowser,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venvDir = Join-Path $repoRoot "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$frontendDir = Join-Path $repoRoot "myapp"
$dependencyStamp = Join-Path $venvDir ".aquatrade_dependencies_ready"

Set-Location $repoRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-PortListening([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1)
}

function Test-Command([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Start-ServiceWindow(
    [string]$Title,
    [string]$Command,
    [ValidateSet("Normal", "Minimized")]
    [string]$WindowStyle = "Minimized"
) {
    $windowCommand = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONUTF8 = '1'
Set-Location '$repoRoot'
$Command
if (`$LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '$Title exited with an error.' -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
"@

    $encodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($windowCommand))
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-EncodedCommand", $encodedCommand `
        -WindowStyle $WindowStyle | Out-Null
}

Write-Host "========================================" -ForegroundColor DarkCyan
Write-Host " AquaTrade Launcher" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor DarkCyan

Write-Step "Checking runtime"

if (-not (Test-Command "node") -or -not (Test-Command "npm")) {
    throw "Node.js/npm was not found. Install Node.js 20 or newer first."
}

if (-not (Test-Path $venvPython)) {
    if (-not (Test-Command "py")) {
        throw "Python Launcher was not found. Install Python 3.12 with the py launcher."
    }

    & py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 was not found. Install Python 3.12 and try again."
    }

    if (-not $CheckOnly) {
        Write-Step "First run: creating the Python 3.12 virtual environment"
        & py -3.12 -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the virtual environment."
        }
    }
}

if ($CheckOnly) {
    Write-Host "Environment check passed." -ForegroundColor Green
    exit 0
}

$requirementsFile = Join-Path $repoRoot "requirements.txt"
$installPythonDependencies = -not (Test-Path $dependencyStamp)
if (-not $installPythonDependencies) {
    $installPythonDependencies =
        (Get-Item $requirementsFile).LastWriteTimeUtc -gt (Get-Item $dependencyStamp).LastWriteTimeUtc
}

if ($installPythonDependencies) {
    Write-Step "First run: installing Python dependencies (this may take a few minutes)"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update pip."
    }
    & $venvPython -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python dependencies."
    }
    New-Item -ItemType File -Path $dependencyStamp -Force | Out-Null
}

$viteCommand = Join-Path $frontendDir "node_modules\.bin\vite.cmd"
if (-not (Test-Path $viteCommand)) {
    Write-Step "First run: installing frontend dependencies (this may take a few minutes)"
    Push-Location $frontendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install frontend dependencies."
        }
    } finally {
        Pop-Location
    }
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:DB_BACKEND = "lancedb"

Write-Step "Starting Redis"
$redisRunning = $null -ne (Get-Process -Name "redis-server" -ErrorAction SilentlyContinue)
if (-not $redisRunning) {
    $redisExe = "C:\Program Files\Redis\redis-server.exe"
    if (Test-Path $redisExe) {
        Start-Process -FilePath $redisExe -WindowStyle Hidden
        Start-Sleep -Milliseconds 800
        $redisRunning = $true
    } elseif (Test-Command "redis-server") {
        Start-Process -FilePath "redis-server" -WindowStyle Hidden
        Start-Sleep -Milliseconds 800
        $redisRunning = $true
    } else {
        Write-Host "Redis is unavailable. Worker is skipped; the base UI and API can still run." -ForegroundColor Yellow
    }
}

Write-Step "Starting backend and frontend"
if (Test-PortListening 5000) {
    Write-Host "Port 5000 is already listening; backend startup skipped." -ForegroundColor Yellow
} else {
    Start-ServiceWindow "AquaTrade Backend" `
        "`$env:DB_BACKEND = 'lancedb'; & '$venvPython' -m server.app"

    $backendDeadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $backendDeadline -and -not (Test-PortListening 5000)) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-PortListening 5000)) {
        Write-Host "Backend is still starting; frontend will use port 5000 when it becomes ready." -ForegroundColor Yellow
    }
}

if ($redisRunning) {
    $workerExists = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*server\worker.py*" } |
        Select-Object -First 1
    if (-not $workerExists) {
        Start-ServiceWindow "AquaTrade Worker" `
            "& '$venvPython' '$repoRoot\server\worker.py'"
    } else {
        Write-Host "Worker is already running; duplicate startup skipped." -ForegroundColor Yellow
    }
}

if (Test-PortListening 5173) {
    Write-Host "Port 5173 is already listening; frontend startup skipped." -ForegroundColor Yellow
} else {
    Start-ServiceWindow "AquaTrade Frontend" `
        "Set-Location '$frontendDir'; & npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"
}

Write-Step "Waiting for services"
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if ((Test-PortListening 5000) -and (Test-PortListening 5173)) {
        break
    }
    Start-Sleep -Milliseconds 500
}

$backendReady = Test-PortListening 5000
$frontendReady = Test-PortListening 5173

Write-Host ""
if ($backendReady -and $frontendReady) {
    Write-Host "AquaTrade is ready." -ForegroundColor Green
} else {
    Write-Host "Some services are not ready. Check their service windows." -ForegroundColor Yellow
}
Write-Host "Frontend: http://127.0.0.1:5173/dashboard"
Write-Host "Backend:  http://127.0.0.1:5000"

if (-not $NoBrowser -and $frontendReady) {
    Start-Process "http://127.0.0.1:5173/dashboard"
}
