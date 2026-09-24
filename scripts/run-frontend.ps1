# 本地启动前端（Next.js dev），并把 /api 代理到后端
# 用法： powershell -ExecutionPolicy Bypass -File scripts\run-frontend.ps1 [-Port 3010] [-BackendPort 8010]
param([int]$Port = 3010, [int]$BackendPort = 8010)

$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "..\frontend"
Set-Location $frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "安装前端依赖..." -ForegroundColor Cyan
    npm install --no-audit --no-fund
}

$env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
Write-Host "前端启动： http://127.0.0.1:$Port  (代理 /api -> $env:BACKEND_URL)" -ForegroundColor Green
npx next dev -H 127.0.0.1 -p $Port
