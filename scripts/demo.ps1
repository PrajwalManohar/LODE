# LODE demo launcher — starts backend + frontend, opens browser, waits for Ctrl+C.
# Usage:  .\scripts\demo.ps1            (start)
#         .\scripts\demo.ps1 -Stop      (stop everything on :8000 and :5173)
#         .\scripts\demo.ps1 -Reset     (delete db + indexes + queues, then exit)
#         .\scripts\demo.ps1 -Smoke     (run headless E2E smoke test, then exit)

param(
    [switch]$Stop,
    [switch]$Reset,
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root

function Stop-OnPort($port) {
    $pids = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -Expand OwningProcess -Unique
    foreach ($p in $pids) {
        Write-Host "  killing PID $p on port $port" -ForegroundColor Yellow
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}

if ($Stop) {
    Write-Host "Stopping LODE servers..." -ForegroundColor Cyan
    Stop-OnPort 8000
    Stop-OnPort 5173
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

if ($Reset) {
    Write-Host "Resetting LODE runtime state (chroma, queues, SOPs)..." -ForegroundColor Cyan
    & .\.venv\Scripts\python.exe -c @"
import shutil
for d in ['data/chroma','data/airtable_queue','data/email_outbox','data/output']:
    shutil.rmtree(d, ignore_errors=True)
print('clean')
"@
    exit 0
}

if ($Smoke) {
    $env:PYTHONIOENCODING = "utf-8"
    Write-Host "Running headless E2E smoke test..." -ForegroundColor Cyan
    & .\.venv\Scripts\python.exe scripts\smoke_test_full.py
    exit $LASTEXITCODE
}

# Default: start everything.
Write-Host "[1/4] Pre-flight checks..." -ForegroundColor Cyan
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw ".venv not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path frontend\node_modules\vite\bin\vite.js)) {
    throw "frontend\node_modules not installed. Run: cd frontend; npm install"
}

# Free the ports in case a previous run hung.
Stop-OnPort 8000
Stop-OnPort 5173

Write-Host "[2/4] Starting backend on :8000..." -ForegroundColor Cyan
$backend = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","backend.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory $root `
    -RedirectStandardOutput "backend.log" -RedirectStandardError "backend.err.log" `
    -PassThru -WindowStyle Hidden

# Wait for backend health.
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2
        if ($r.status -eq "ok") { break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if ((Get-Date) -ge $deadline) {
    throw "Backend failed to come up. See backend.log / backend.err.log"
}
Write-Host "  backend ready (pid $($backend.Id))" -ForegroundColor Green

Write-Host "[3/4] Starting frontend on :5173..." -ForegroundColor Cyan
$vite = (Resolve-Path "frontend\node_modules\vite\bin\vite.js").Path
$frontend = Start-Process -FilePath "node" `
    -ArgumentList $vite,"--host","127.0.0.1","--port","5173" `
    -WorkingDirectory (Join-Path $root "frontend") `
    -RedirectStandardOutput "frontend.log" -RedirectStandardError "frontend.err.log" `
    -PassThru -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest http://127.0.0.1:5173 -TimeoutSec 2 -UseBasicParsing | Out-Null
        break
    } catch { Start-Sleep -Milliseconds 500 }
}
if ((Get-Date) -ge $deadline) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    throw "Frontend failed to come up. See frontend.log / frontend.err.log"
}
Write-Host "  frontend ready (pid $($frontend.Id))" -ForegroundColor Green

Write-Host "[4/4] Opening browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  LODE is running" -ForegroundColor Green
Write-Host "  UI:        http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "  API:       http://127.0.0.1:8000/api" -ForegroundColor Green
Write-Host "  API docs:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  Email demos: DEMO_SCENARIOS.md" -ForegroundColor Green
Write-Host "  Stop with:  .\scripts\demo.ps1 -Stop  (or Ctrl+C here)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

# Keep this window alive; trap Ctrl+C and tear down children cleanly.
try {
    while ($true) {
        if ($backend.HasExited) { Write-Host "Backend died." -ForegroundColor Red; break }
        if ($frontend.HasExited) { Write-Host "Frontend died." -ForegroundColor Red; break }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Cyan
    if (-not $backend.HasExited)  { Stop-Process -Id $backend.Id  -Force -ErrorAction SilentlyContinue }
    if (-not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    Stop-OnPort 8000
    Stop-OnPort 5173
    Write-Host "Done." -ForegroundColor Green
}
