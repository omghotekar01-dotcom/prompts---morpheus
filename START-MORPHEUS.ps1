$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Activate = Join-Path $Venv "Scripts\Activate.ps1"

Write-Host ""
Write-Host "MORPHEUS Launcher" -ForegroundColor Cyan
Write-Host "Repository: $Root"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH. Install a supported Python version and restart the terminal."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is not available on PATH. Install Node.js 20+ and restart the terminal."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not available on PATH. Reinstall Node.js with npm enabled."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/4] Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $Backend
    python -m venv .venv
    Pop-Location
}

Write-Host "[2/4] Checking backend dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip show uvicorn *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
}

Write-Host "[3/4] Checking frontend dependencies..." -ForegroundColor Yellow
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Push-Location $Frontend
    npm install --no-audit --no-fund
    Pop-Location
}

Write-Host "[4/4] Starting MORPHEUS services..." -ForegroundColor Yellow

$BackendCommand = "Set-Location '$Backend'; & '$Activate'; python -m uvicorn app.server:app --reload --port 8000"
$FrontendCommand = "Set-Location '$Frontend'; npm run dev"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand
Start-Sleep -Milliseconds 800
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand

Write-Host ""
Write-Host "MORPHEUS is starting." -ForegroundColor Green
Write-Host "UI:       http://localhost:5173"
Write-Host "API:      http://localhost:8000"
Write-Host "API Docs: http://localhost:8000/docs"
Write-Host "v2:       http://localhost:8000/api/v2/completion"
Write-Host ""
Write-Host "Keep both spawned terminals open while using MORPHEUS."
