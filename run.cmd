@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
  echo Installing uv...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
  echo uv is not on PATH. Install from https://docs.astral.sh/uv/ then run this file again.
  pause
  exit /b 1
)

uv sync --all-groups
if errorlevel 1 (
  echo uv sync failed.
  pause
  exit /b 1
)

uv run streamlit run streamlit_app.py --server.headless true --server.address localhost
if errorlevel 1 pause
endlocal
