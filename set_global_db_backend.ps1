# PowerShell 脚本：全局设置 DB_BACKEND 环境变量
# 需要以管理员身份运行

# 检查是否以管理员身份运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "错误：此脚本需要管理员权限！" -ForegroundColor Red
    Write-Host "请右键点击 PowerShell，选择'以管理员身份运行'，然后重新执行此脚本。" -ForegroundColor Yellow
    exit 1
}

# 设置用户级环境变量（推荐）
Write-Host "正在设置用户级环境变量 DB_BACKEND=lancedb..." -ForegroundColor Green
[Environment]::SetEnvironmentVariable("DB_BACKEND", "lancedb", "User")

# 验证设置
$value = [Environment]::GetEnvironmentVariable("DB_BACKEND", "User")
if ($value -eq "lancedb") {
    Write-Host "✓ 环境变量设置成功！" -ForegroundColor Green
    Write-Host "  变量名: DB_BACKEND" -ForegroundColor Cyan
    Write-Host "  变量值: $value" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "注意：" -ForegroundColor Yellow
    Write-Host "  1. 需要重启所有已打开的终端窗口才能生效" -ForegroundColor Yellow
    Write-Host "  2. 或者重新登录 Windows 系统" -ForegroundColor Yellow
    Write-Host "  3. 设置后，所有新打开的终端都会自动使用此环境变量" -ForegroundColor Yellow
} else {
    Write-Host "✗ 环境变量设置失败！" -ForegroundColor Red
    exit 1
}

# 可选：同时设置系统级环境变量（需要更高权限，通常不推荐）
# [Environment]::SetEnvironmentVariable("DB_BACKEND", "lancedb", "Machine")

