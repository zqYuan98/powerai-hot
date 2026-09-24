$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$tempEnv = Join-Path $projectRoot "backend\.compose-test.env"
$previousEnvFile = $env:BACKEND_ENV_FILE
$previousProject = $env:COMPOSE_PROJECT_NAME
$locationPushed = $false

if (Test-Path -LiteralPath $tempEnv) {
    throw "Refusing to overwrite existing temporary environment: $tempEnv"
}

$envLines = @(
    "DEBUG=false",
    "WORKSPACE_TOKEN=workspace-7cbb1b8c7ad942d69c8b",
    "ADMIN_TOKEN=admin-51bd4f76a84a4b0b89f18c",
    "SESSION_SECRET=MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
    "SESSION_COOKIE_SECURE=false",
    "SESSION_TTL_SECONDS=28800",
    "APP_ORIGIN=http://127.0.0.1",
    "AUTO_CRAWL_ENABLED=true",
    "DEEPSEEK_API_KEY=",
    "EMBEDDING_API_KEY="
)

try {
    [System.IO.File]::WriteAllLines($tempEnv, $envLines, [System.Text.UTF8Encoding]::new($false))
    $env:BACKEND_ENV_FILE = "./backend/.compose-test.env"
    $env:COMPOSE_PROJECT_NAME = "powerai-baseline-check"
    Push-Location $projectRoot
    $locationPushed = $true

    docker compose config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose config failed" }
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        docker compose exec -T backend python -c "import httpx; r=httpx.get('http://127.0.0.1:8000/health', timeout=2); r.raise_for_status()" 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "backend health check timed out" }

    $pipelineCheck = @'
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    auth = client.post("/api/auth/session", json={"scope": "admin", "token": "admin-51bd4f76a84a4b0b89f18c"})
    auth.raise_for_status()
    response = client.get("/api/admin/pipeline")
    response.raise_for_status()
    monitor = response.json()["monitor"]
    required = {"papers", "digest", "weekly"}
    if monitor.get("running") is not True or not required.issubset(monitor.get("next_runs", {})):
        raise SystemExit(f"scheduler monitor mismatch: {monitor}")
'@
    docker compose exec -T backend python -c $pipelineCheck
    if ($LASTEXITCODE -ne 0) { throw "scheduler runtime assertion failed" }

    $processes = docker compose top
    if ($LASTEXITCODE -ne 0) { throw "docker compose top failed" }
    if (($processes | Out-String) -match "(?i)celery|worker --beat") {
        throw "unexpected Celery beat process found"
    }
}
finally {
    try {
        if ($locationPushed) {
            docker compose down -v 2>$null | Out-Null
            Pop-Location
            $locationPushed = $false
        }
    } catch {
        Write-Warning "Compose cleanup failed: $($_.Exception.Message)"
    }
    if (Test-Path -LiteralPath $tempEnv) { Remove-Item -LiteralPath $tempEnv -Force }
    $env:BACKEND_ENV_FILE = $previousEnvFile
    $env:COMPOSE_PROJECT_NAME = $previousProject
}
