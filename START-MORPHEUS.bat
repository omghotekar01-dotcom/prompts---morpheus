@echo off
setlocal
cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell is required to launch MORPHEUS.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START-MORPHEUS.ps1"
if errorlevel 1 (
  echo.
  echo MORPHEUS launcher failed. Review the message above.
  pause
  exit /b 1
)

endlocal
