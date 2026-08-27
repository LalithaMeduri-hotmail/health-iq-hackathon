#Requires -Version 7.0
<#
.SYNOPSIS
  Runs the Health IQ backend (FastAPI/uvicorn) and frontend (Vite) together for local development.

.DESCRIPTION
  Starts both dev servers as background jobs in this session. Requires `.env` (repo root, copied
  from `.env.example`) and Azure resources provisioned per infra/README.md. Requires `uv`
  (https://docs.astral.sh/uv/) and Node.js/npm.

.EXAMPLE
  ./scripts/run_local.ps1
#>
param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

if (-not (Test-Path (Join-Path $repoRoot '.env'))) {
  Write-Warning '.env not found at repo root - copy .env.example to .env and fill in AZURE_KEY_VAULT_URI first.'
}

Write-Host "Starting backend on :$BackendPort ..." -ForegroundColor Cyan
$backend = Start-Job -Name 'healthiq-backend' -ScriptBlock {
  param($root, $port)
  Set-Location (Join-Path $root 'backend')
  uv run uvicorn app.main:app --reload --port $port
} -ArgumentList $repoRoot, $BackendPort

Write-Host "Starting frontend on :$FrontendPort ..." -ForegroundColor Cyan
$frontend = Start-Job -Name 'healthiq-frontend' -ScriptBlock {
  param($root, $port)
  Set-Location (Join-Path $root 'frontend')
  npm run dev -- --port $port
} -ArgumentList $repoRoot, $FrontendPort

Write-Host 'Both dev servers are starting as background jobs (Get-Job / Receive-Job / Stop-Job).' -ForegroundColor Green
Write-Host "  Backend:  http://localhost:$BackendPort/health"
Write-Host "  Frontend: http://localhost:$FrontendPort"

try {
  Receive-Job -Job $backend, $frontend -Wait
}
finally {
  Stop-Job -Job $backend, $frontend -ErrorAction SilentlyContinue
  Remove-Job -Job $backend, $frontend -ErrorAction SilentlyContinue
}
