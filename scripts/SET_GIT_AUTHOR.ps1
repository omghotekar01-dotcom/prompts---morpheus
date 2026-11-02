# Configure the actual local Git author for future MORPHEUS commits.
# Connector-generated remote commits use the connected GitHub account's author.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "Clone MORPHEUS with git before running this script. No .git directory found at $Root"
}
& git -C $Root config --local user.name "Om Ghotekar"
if ($LASTEXITCODE -ne 0) { throw "Failed to set git user.name" }
& git -C $Root config --local user.email "omghotekar01@gmail.com"
if ($LASTEXITCODE -ne 0) { throw "Failed to set git user.email" }
Write-Host "Local MORPHEUS Git author:" -ForegroundColor Green
& git -C $Root config --local --get user.name
& git -C $Root config --local --get user.email
