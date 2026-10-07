@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo The app environment is not set up. See README.md for setup instructions.
  pause
  exit /b 1
)
start "Fuel Cell Project Hub" ".venv\Scripts\pythonw.exe" -m app.main
