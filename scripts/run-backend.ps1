# 本地启动后端（SQLite，零配置，无需 Docker / PostgreSQL）
# 用法： powershell -ExecutionPolicy Bypass -File scripts\run-backend.ps1 [-Port 8010]
param([int]$Port = 8010)

$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $backend

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Cyan
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
}

if (-not (Test-Path "powerai_hot.db")) {
    Write-Host "初始化数据库、基础信源与订阅配置..." -ForegroundColor Cyan
    .\.venv\Scripts\python.exe -m models.seed
}

$bytesToUrlSafe = {
    param([int]$Length = 32)
    $bytes = [byte[]]::new($Length)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    [Convert]::ToBase64String($bytes).TrimEnd('=') -replace '\+', '-' -replace '/', '_'
}
if ([string]::IsNullOrWhiteSpace($env:WORKSPACE_TOKEN)) { $env:WORKSPACE_TOKEN = & $bytesToUrlSafe 32 }
if ([string]::IsNullOrWhiteSpace($env:ADMIN_TOKEN)) { $env:ADMIN_TOKEN = & $bytesToUrlSafe 32 }
if ([string]::IsNullOrWhiteSpace($env:SESSION_SECRET)) { $env:SESSION_SECRET = & $bytesToUrlSafe 32 }
$env:APP_ORIGIN = "http://127.0.0.1:3010"
$env:SESSION_COOKIE_SECURE = "false"
$env:AUTO_CRAWL_ENABLED = if ($env:AUTO_CRAWL_ENABLED) { $env:AUTO_CRAWL_ENABLED } else { "false" }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
Write-Host "Workspace access code: $env:WORKSPACE_TOKEN" -ForegroundColor Yellow
Write-Host "Admin access code: $env:ADMIN_TOKEN" -ForegroundColor Yellow
Write-Host "Codes are process-local; SESSION_SECRET is never written to disk or logs." -ForegroundColor DarkGray
Write-Host "后端启动： http://127.0.0.1:$Port  (文档 /docs)" -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port $Port --reload
