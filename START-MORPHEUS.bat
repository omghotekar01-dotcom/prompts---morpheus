@echo off
setlocal
cd /d "%~dp0"

echo.
echo Starting MORPHEUS...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START-MORPHEUS.ps1"

if errorlevel 1 (
  echo.
  echo MORPHEUS launcher exited with an error.
  pause
)
