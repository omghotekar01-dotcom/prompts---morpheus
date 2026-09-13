$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Activate = Join-Path $Venv "Scripts\Activate.ps1"

function ConvertTo-PsLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-AvailablePort([int]$StartPort, [int]$EndPort) {
    for ($port = $StartPort; $port -le $EndPort; $port++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            $listener.Start()
            return $port
        }
        catch {
            # Port is already in use or Windows has reserved/blocked it.
        }
        finally {
            if ($null -ne $listener) {
                try { $listener.Stop() } catch { }
            }
        }
    }
    throw "No usable local TCP port was found in range $StartPort-$EndPort."
}

function Wait-ForEndpoint([string]$Url, [int]$TimeoutSeconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {
            # Service may still be starting. Retry until the timeout expires.
        }
        Start-Sleep -Milliseconds 350
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

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
    Write-Host "[1/5] Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $Backend
    python -m venv .venv
    Pop-Location
}
else {
    Write-Host "[1/5] Backend virtual environment ready." -ForegroundColor DarkGray
}

Write-Host "[2/5] Checking backend dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip show uvicorn *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
}

Write-Host "[3/5] Checking frontend dependencies..." -ForegroundColor Yellow
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Push-Location $Frontend
    npm install --no-audit --no-fund
    Pop-Location
}

Write-Host "[4/5] Selecting safe local ports and starting backend..." -ForegroundColor Yellow
$BackendPort = Get-AvailablePort 8000 8099
$BackendUrl = "http://127.0.0.1:$BackendPort"
$BackendLiteral = ConvertTo-PsLiteral $Backend
$ActivateLiteral = ConvertTo-PsLiteral $Activate
$BackendCommand = "Set-Location $BackendLiteral; & $ActivateLiteral; python -m uvicorn app.server:app --host 127.0.0.1 --port $BackendPort"
$BackendProcess = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand -PassThru

Write-Host "      Backend port: $BackendPort" -ForegroundColor Cyan
if (-not (Wait-ForEndpoint "$BackendUrl/api/health" 35)) {
    throw "MORPHEUS backend did not become healthy on $BackendUrl. Check the spawned backend terminal for the exact error."
}
Write-Host "      Backend health: ready" -ForegroundColor Green

Write-Host "[5/5] Starting frontend with the verified backend route..." -ForegroundColor Yellow
$FrontendPort = Get-AvailablePort 5173 5273
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$FrontendLiteral = ConvertTo-PsLiteral $Frontend
$FrontendCommand = "Set-Location $FrontendLiteral; `$env:MORPHEUS_BACKEND_URL='$BackendUrl'; `$env:MORPHEUS_FRONTEND_PORT='$FrontendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort --strictPort"
$FrontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand -PassThru

if (-not (Wait-ForEndpoint $FrontendUrl 35)) {
    throw "MORPHEUS frontend did not become reachable on $FrontendUrl. Check the spawned frontend terminal for the exact error."
}

Write-Host ""
Write-Host "MORPHEUS is ready." -ForegroundColor Green
Write-Host "UI:       $FrontendUrl"
Write-Host "API:      $BackendUrl"
Write-Host "API Docs: $BackendUrl/docs"
Write-Host "v2:       $BackendUrl/api/v2/completion"
Write-Host ""
Write-Host "Keep both spawned terminals open while using MORPHEUS."
Write-Host "The launcher selected free ports automatically; do not assume port 8000/5173." -ForegroundColor DarkGray

Start-Process $FrontendUrl
