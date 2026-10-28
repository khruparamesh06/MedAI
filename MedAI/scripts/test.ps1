<#
.SYNOPSIS
  Run all automated checks: backend tests, frontend tests, lint, type-check and production build.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$failed = @()

Write-Host "`n==> Backend tests (pytest)" -ForegroundColor Cyan
Push-Location (Join-Path $Root 'backend')
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { $failed += 'backend tests' }
Pop-Location

Push-Location (Join-Path $Root 'frontend')
Write-Host "`n==> Frontend tests (vitest)" -ForegroundColor Cyan
npm test
if ($LASTEXITCODE -ne 0) { $failed += 'frontend tests' }
Write-Host "`n==> Frontend lint (oxlint)" -ForegroundColor Cyan
npm run lint
if ($LASTEXITCODE -ne 0) { $failed += 'lint' }
Write-Host "`n==> Frontend production build" -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) { $failed += 'build' }
Pop-Location

if ($failed.Count) { Write-Host "`nFAILED: $($failed -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "`nAll checks passed." -ForegroundColor Green
