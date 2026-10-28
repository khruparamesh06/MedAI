<#
.SYNOPSIS
  Apply database migrations (and optionally load synthetic demo accounts).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\init-db.ps1
  powershell -ExecutionPolicy Bypass -File scripts\init-db.ps1 -SeedDemo
#>
param([switch]$SeedDemo)

$ErrorActionPreference = 'Stop'
$Backend = Join-Path (Split-Path -Parent $PSScriptRoot) 'backend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Virtual environment not found. Run scripts\setup.ps1 first.' }

Push-Location $Backend
try {
    & $Python -m app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Check DATABASE_URL in .env.' }
    Write-Host 'Database is up to date.' -ForegroundColor Green
    if ($SeedDemo) { & $Python -m app.cli seed-demo }
} finally { Pop-Location }
