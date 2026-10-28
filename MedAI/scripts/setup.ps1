<#
.SYNOPSIS
  One-time MedAI setup on Windows: Python virtual environment, backend + frontend dependencies,
  .env file with a generated secret, and database migrations.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -WithAI   # also installs PyTorch (~1 GB)
#>
param(
    [switch]$WithAI,
    [switch]$SeedDemo
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step 'Checking prerequisites'
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) { throw 'Python launcher "py" not found. Install Python 3.12 from python.org (tick "Add to PATH").' }
& py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Install it from https://www.python.org/downloads/' }
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw 'Node.js not found. Install Node.js 20 LTS or newer from https://nodejs.org/' }
node --version

Step 'Creating Python virtual environment (backend\.venv)'
if (-not (Test-Path $Python)) { & py -3.12 -m venv (Join-Path $Backend '.venv') }
& $Python -m pip install --upgrade pip --quiet
& $Python -m pip install -r (Join-Path $Backend 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installing backend requirements failed.' }

if ($WithAI) {
    Step 'Installing optional AI stack (PyTorch CPU, TorchXRayVision)'
    & $Python -m pip install -r (Join-Path $Backend 'requirements-ai.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installing AI requirements failed.' }
}

Step 'Creating .env'
$EnvFile = Join-Path $Root '.env'
if (Test-Path $EnvFile) {
    Write-Host '.env already exists - leaving it unchanged.'
} else {
    $secret = & $Python -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content (Join-Path $Root '.env.example')) -replace '^JWT_SECRET_KEY=$', "JWT_SECRET_KEY=$secret" |
        Set-Content -Path $EnvFile -Encoding utf8
    Write-Host 'Created .env with a newly generated JWT_SECRET_KEY.'
}

Step 'Applying database migrations'
Push-Location $Backend
try {
    & $Python -m app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
    if ($SeedDemo) { & $Python -m app.cli seed-demo }
} finally { Pop-Location }

Step 'Installing frontend dependencies (npm install)'
Push-Location $Frontend
try {
    npm install --no-fund --no-audit
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
} finally { Pop-Location }

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host 'Next steps:'
Write-Host '  1. Create an administrator:  backend\.venv\Scripts\python -m app.cli create-admin --email you@example.com  (run inside backend\)'
Write-Host '     or load demo accounts:    scripts\setup.ps1 -SeedDemo   (development only)'
Write-Host '  2. Start the app:            powershell -ExecutionPolicy Bypass -File scripts\start.ps1'
