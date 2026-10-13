@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m blink_emg_app %*
) else if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" -m blink_emg_app %*
) else (
  echo First run setup.ps1 to install the project dependencies.
  pause
  exit /b 1
)
if errorlevel 1 pause
