$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

function ConvertTo-PsLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
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
    try {
        python -m venv .venv
        Assert-NativeSuccess "Creating backend virtual environment"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[1/5] Backend virtual environment ready." -ForegroundColor DarkGray
}

if (-not (Test-Path $VenvPython)) {
    throw "Backend virtual environment was not created correctly: $VenvPython is missing."
}

Write-Host "[2/5] Checking backend dependencies..." -ForegroundColor Yellow

# IMPORTANT:
# Avoid package-manager metadata probes for an absent dependency here. On a
# fresh virtual environment, that style of probe can write a harmless
# "Package(s) not found" message to stderr. Under Windows PowerShell with
# $ErrorActionPreference='Stop', stderr from the probe can become a terminating
# NativeCommandError before the installer gets a chance to run.
& $VenvPython -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('uvicorn') else 1)"
$BackendDependenciesReady = ($LASTEXITCODE -eq 0)

if (-not $BackendDependenciesReady) {
    Write-Host "      Backend dependencies missing; installing..." -ForegroundColor Yellow
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    Assert-NativeSuccess "Upgrading backend packaging tools"

    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
    Assert-NativeSuccess "Installing backend dependencies"

    & $VenvPython -c "import uvicorn, fastapi, pydantic"
    Assert-NativeSuccess "Verifying backend dependencies"
    Write-Host "      Backend dependencies: ready" -ForegroundColor Green
}
else {
    Write-Host "      Backend dependencies: ready" -ForegroundColor DarkGray
}

Write-Host "[3/5] Checking frontend dependencies..." -ForegroundColor Yellow
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "      Frontend dependencies missing; installing..." -ForegroundColor Yellow
    Push-Location $Frontend
    try {
        npm install --no-audit --no-fund
        Assert-NativeSuccess "Installing frontend dependencies"
    }
    finally {
        Pop-Location
    }
    Write-Host "      Frontend dependencies: ready" -ForegroundColor Green
}
else {
    Write-Host "      Frontend dependencies: ready" -ForegroundColor DarkGray
}

# Native C++ is mandatory for search. Prefer a checked, CI-built binary pair
# when the user does not have a compiler installed. No Python search fallback.
Write-Host "[4/5] Preparing native C++20 DSA engines..." -ForegroundColor Yellow
$NativeExecutable = $null
$CsvProfilerExecutable = $null
$PrebuiltDir = Join-Path $Root "bin\windows-x64"
$PrebuiltSearch = Join-Path $PrebuiltDir "morpheus_native_search.exe"
$PrebuiltCsv = Join-Path $PrebuiltDir "morpheus_csv_profile.exe"
$PrebuiltManifest = Join-Path $PrebuiltDir "SHA256.json"

# If GitHub CLI is installed and authenticated, retrieve this commit's
# official Windows C++ artifact automatically. Never retrieve arbitrary EXEs.
if (-not ((Test-Path $PrebuiltSearch) -and (Test-Path $PrebuiltCsv) -and
          (Test-Path $PrebuiltManifest)) -and (Get-Command gh -ErrorAction SilentlyContinue)) {
    $RepoName = "omghotekar01-dotcom/prompts---morpheus"
    $HeadSha = (& git -C $Root rev-parse HEAD).Trim()
    Assert-NativeSuccess "Identifying current source commit"
    $ArtifactName = "morpheus-native-windows-x64-$HeadSha"
    Write-Host "      Checking GitHub Actions for precompiled C++20 engines..." -ForegroundColor Cyan
    try {
        $RawArtifacts = & gh api "repos/$RepoName/actions/artifacts?per_page=100" 2>$null
        if ($LASTEXITCODE -eq 0 -and $RawArtifacts) {
            $Artifacts = ($RawArtifacts -join "`n" | ConvertFrom-Json).artifacts
            $Available = @($Artifacts | Where-Object { $_.name -ceq $ArtifactName -and -not $_.expired })
            if ($Available.Count -gt 0) {
                $DownloadDir = Join-Path $Root "bin\\.native-ci-download"
                if (Test-Path $DownloadDir) {
                    Remove-Item -LiteralPath $DownloadDir -Recurse -Force
                }
                New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
                $RunId = [string]$Available[0].workflow_run.id
                & gh run download $RunId -R $RepoName -n $ArtifactName -D $DownloadDir
                if ($LASTEXITCODE -eq 0 -and
                    (Test-Path (Join-Path $DownloadDir "morpheus_native_search.exe")) -and
                    (Test-Path (Join-Path $DownloadDir "morpheus_csv_profile.exe")) -and
                    (Test-Path (Join-Path $DownloadDir "SHA256.json"))) {
                    New-Item -ItemType Directory -Path $PrebuiltDir -Force | Out-Null
                    foreach ($Name in @("morpheus_native_search.exe", "morpheus_csv_profile.exe", "SHA256.json")) {
                        Copy-Item -LiteralPath (Join-Path $DownloadDir $Name) -Destination (Join-Path $PrebuiltDir $Name) -Force
                    }
                    Write-Host "      Downloaded native C++ engines; verifying provenance below." -ForegroundColor Green
                }
                Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Write-Host "      GitHub CLI artifact download unavailable: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

if ((Test-Path $PrebuiltSearch) -and (Test-Path $PrebuiltCsv)) {
    if (-not (Test-Path $PrebuiltManifest)) {
        throw "Native executables exist, but SHA256.json is missing. Extract the entire official CI artifact to $PrebuiltDir. Unverified binaries are not executed."
    }
    $Manifest = Get-Content -LiteralPath $PrebuiltManifest -Raw | ConvertFrom-Json
    if ($Manifest.protocol -ne "MORPHEUS_WINDOWS_NATIVE_V1") {
        throw "Prebuilt native engine manifest has an unsupported format."
    }
    $CurrentCommit = (& git -C $Root rev-parse HEAD).Trim()
    Assert-NativeSuccess "Identifying checked-out MORPHEUS commit"
    if ($Manifest.source_commit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Prebuilt manifest has an invalid source commit."
    }
    if ($Manifest.source_commit -ne $CurrentCommit) {
        # Allow an earlier verified CI bundle when only API/UI/docs/launcher
        # changed after it: both native sources and their CMake build recipe
        # must be identical to the artifact-producing commit.
        $NativeSources = @(
            "core/CMakeLists.txt",
            "core/src/native_search.cpp",
            "core/src/csv_profile.cpp",
            "core/include/morpheus/native_search.hpp",
            "core/include/morpheus/csv_profile.hpp"
        )
        & git -C $Root cat-file -e "$($Manifest.source_commit)^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Native artifact source commit is not in local Git history. Download a matching artifact."
        }
        & git -C $Root merge-base --is-ancestor $Manifest.source_commit $CurrentCommit
        if ($LASTEXITCODE -ne 0) {
            throw "Native artifact is not from an ancestor of the current code. Download the exact current artifact."
        }
        & git -C $Root diff --quiet $Manifest.source_commit $CurrentCommit -- @NativeSources
        if ($LASTEXITCODE -ne 0) {
            throw "Native C++ sources differ from the precompiled artifact. Download a matching artifact."
        }
        & git -C $Root diff --quiet -- @NativeSources
        if ($LASTEXITCODE -ne 0) {
            throw "Native C++ sources have uncommitted edits; rebuild the binaries rather than using an old artifact."
        }
        & git -C $Root diff --cached --quiet -- @NativeSources
        if ($LASTEXITCODE -ne 0) {
            throw "Native C++ sources have staged edits; rebuild the binaries rather than using an old artifact."
        }
        Write-Host "      Native C++ sources unchanged since artifact commit; using verified compatible binaries." -ForegroundColor Green
    }
    foreach ($Name in @("morpheus_native_search.exe", "morpheus_csv_profile.exe")) {
        $FilePath = Join-Path $PrebuiltDir $Name
        $Entry = @($Manifest.files | Where-Object { $_.name -ceq $Name })
        if ($Entry.Count -ne 1 -or $Entry[0].sha256 -notmatch '^[A-Fa-f0-9]{64}$') {
            throw "Native engine manifest is missing a valid SHA-256 for $Name."
        }
        $ActualHash = (Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash
        if ($ActualHash -ine $Entry[0].sha256) {
            throw "Prebuilt $Name failed SHA-256 integrity check. Refusing to execute it."
        }
    }
    $NativeExecutable = $PrebuiltSearch
    $CsvProfilerExecutable = $PrebuiltCsv
    Write-Host "      Verified CI-built C++ executables for the current Git commit." -ForegroundColor Green
}
else {
    if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
        throw "Missing CMake. Install CMake + Desktop development with C++, or download the CI-built native Windows artifact to bin\windows-x64. Neither native engine can be replaced by Python."
    }

    # This dedicated directory avoids stale build/core CMake generator caches.
    $CoreBuild = Join-Path $Root "build\native-windows"
    & cmake -S (Join-Path $Root "core") -B $CoreBuild
    if ($LASTEXITCODE -ne 0) {
        throw @"
CMake could not configure a C++20 compiler.
GitHub CI has Windows native artifacts even if this machine has no C++ toolchain.
If 'gh' is installed and authenticated, the launcher downloads them automatically.
Otherwise, download the artifact for this Git commit at:
https://github.com/omghotekar01-dotcom/prompts---morpheus/actions/workflows/ci.yml
and extract the two executables plus SHA256.json to the bin\\windows-x64 folder.
Visual Studio was detected but its C++ workload/toolset may be absent.
Open 'Visual Studio Installer' -> 'Modify' -> 'Desktop development with C++'.
Install MSVC x64/x86 Build Tools and a Windows SDK, restart PowerShell,
then launch MORPHEUS again.
Alternatively download the repository's verified Windows native engines from
GitHub Actions and extract the artifact into:
$PrebuiltDir
Build directory: $CoreBuild
No Python-only DSA fallback has been enabled.
"@
    }
    & cmake --build $CoreBuild --config Release --target morpheus_native_search morpheus_csv_profile
    Assert-NativeSuccess "Compiling the native C++20 DSA engines"

    $NativeExecutable = Join-Path $CoreBuild "Release\morpheus_native_search.exe"
    if (-not (Test-Path $NativeExecutable)) {
        $NativeExecutable = Join-Path $CoreBuild "morpheus_native_search.exe"
    }
    $CsvProfilerExecutable = Join-Path $CoreBuild "Release\morpheus_csv_profile.exe"
    if (-not (Test-Path $CsvProfilerExecutable)) {
        $CsvProfilerExecutable = Join-Path $CoreBuild "morpheus_csv_profile.exe"
    }
}
if (-not (Test-Path $NativeExecutable)) {
    throw "The required C++ search executable was not found. Native-only execution is enforced."
}
if (-not (Test-Path $CsvProfilerExecutable)) {
    throw "The required C++ CSV profiler executable was not found. Native-only execution is enforced."
}
$NativeExecutableLiteral = ConvertTo-PsLiteral $NativeExecutable
$CsvProfilerExecutableLiteral = ConvertTo-PsLiteral $CsvProfilerExecutable
Write-Host "      C++ optimizer: $NativeExecutable" -ForegroundColor Green
Write-Host "      C++ profiler:  $CsvProfilerExecutable" -ForegroundColor Green

Write-Host "[4/5] Selecting safe local ports and starting backend..." -ForegroundColor Yellow
$BackendPort = Get-AvailablePort 8000 8099
$BackendUrl = "http://127.0.0.1:$BackendPort"
$BackendLiteral = ConvertTo-PsLiteral $Backend
$VenvPythonLiteral = ConvertTo-PsLiteral $VenvPython

# Invoke the venv Python directly instead of depending on Activate.ps1.
# This avoids execution-policy/profile differences in the spawned terminal.
$BackendCommand = "Set-Location $BackendLiteral; `$env:MORPHEUS_SEARCH_BACKEND='native'; `$env:MORPHEUS_NATIVE_SEARCH_EXECUTABLE=$NativeExecutableLiteral; `$env:MORPHEUS_CSV_PROFILE_EXECUTABLE=$CsvProfilerExecutableLiteral; & $VenvPythonLiteral -m uvicorn app.server:app --host 127.0.0.1 --port $BackendPort"
$BackendProcess = Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand -PassThru

Write-Host "      Backend port: $BackendPort" -ForegroundColor Cyan
if (-not (Wait-ForEndpoint "$BackendUrl/api/health" 45)) {
    if ($null -ne $BackendProcess -and -not $BackendProcess.HasExited) {
        try { Stop-Process -Id $BackendProcess.Id -Force } catch { }
    }
    throw "MORPHEUS backend did not become healthy on $BackendUrl. Check the spawned backend terminal for the exact error."
}
Write-Host "      Backend health: ready" -ForegroundColor Green

Write-Host "[5/5] Starting frontend with the verified backend route..." -ForegroundColor Yellow
$FrontendPort = Get-AvailablePort 5173 5273
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$FrontendLiteral = ConvertTo-PsLiteral $Frontend
$FrontendCommand = "Set-Location $FrontendLiteral; `$env:MORPHEUS_BACKEND_URL='$BackendUrl'; `$env:MORPHEUS_FRONTEND_PORT='$FrontendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort --strictPort"
$FrontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand -PassThru

if (-not (Wait-ForEndpoint $FrontendUrl 45)) {
    if ($null -ne $FrontendProcess -and -not $FrontendProcess.HasExited) {
        try { Stop-Process -Id $FrontendProcess.Id -Force } catch { }
    }
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
