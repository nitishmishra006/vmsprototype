# Start the backend (:8000) and frontend (:3000) together on Windows.
# Usage: .\scripts\dev.ps1     (closes both windows on Ctrl-C in this one)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "backend\.venv")) {
    Write-Error @"
backend\.venv not found. Create it first:
  cd backend
  python -m venv .venv
  .venv\Scripts\activate
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
"@
}

if (-not (Test-Path "frontend\node_modules")) {
    Write-Error "frontend\node_modules not found. Run: cd frontend; npm install"
}

$backend = Start-Process -PassThru -NoNewWindow -FilePath "cmd.exe" -ArgumentList @(
    "/c",
    "cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000 --log-config log_config.json"
)

$frontend = Start-Process -PassThru -NoNewWindow -FilePath "cmd.exe" -ArgumentList @(
    "/c",
    "cd frontend && npm run dev -- --port 3000"
)

Write-Host "backend  http://localhost:8000  (docs at /docs)"
Write-Host "frontend http://localhost:3000"
Write-Host "Press Ctrl-C to stop both."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
}
finally {
    foreach ($p in @($backend, $frontend)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
