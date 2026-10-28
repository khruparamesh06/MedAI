<#
.SYNOPSIS
  Start the MedAI backend (http://localhost:8000) and frontend (http://localhost:5173)
  in two new PowerShell windows. Close those windows, or run scripts\stop.ps1, to stop.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) { throw 'Virtual environment not found. Run scripts\setup.ps1 first.' }
if (-not (Test-Path (Join-Path $Root '.env'))) { throw '.env not found. Run scripts\setup.ps1 (or copy .env.example to .env).' }
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) { throw 'Frontend dependencies missing. Run: cd frontend; npm install' }

Write-Host 'Applying any pending database migrations...'
Push-Location $Backend
try {
    & $Python -m app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
} finally { Pop-Location }

function Quote([string]$s) { "'" + $s.Replace("'", "''") + "'" }  # PowerShell single-quoted literal
Start-Process powershell -WorkingDirectory $Backend -ArgumentList '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle='MedAI backend'; & $(Quote $Python) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -WorkingDirectory $Frontend -ArgumentList '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle='MedAI frontend'; npm run dev"

Write-Host ''
Write-Host 'MedAI is starting in two new windows:' -ForegroundColor Green
Write-Host '  Frontend : http://localhost:5173'
Write-Host '  API      : http://localhost:8000/api/health'
Write-Host '  Swagger  : http://localhost:8000/docs'
Write-Host 'Stop with:  powershell -ExecutionPolicy Bypass -File scripts\stop.ps1'
