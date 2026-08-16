@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Personal finance agent
echo.
echo  Personal finance agent
echo  Uses a project .venv created by uv. Leave this window open.
echo.

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\uv;%PATH%"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

where uv >nul 2>&1
if errorlevel 1 (
  echo [setup] uv not found. Installing uv...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  if errorlevel 1 (
    echo [setup] uv install failed. Install from https://docs.astral.sh/uv/ then double-click run.cmd again.
    goto :fail
  )
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\uv;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>&1
if errorlevel 1 if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>&1
if errorlevel 1 (
  echo [setup] uv is still not on PATH. Close this window and run run.cmd again.
  echo         Or install from https://docs.astral.sh/uv/
  goto :fail
)

echo [setup] Ensuring Python 3.11+ is available to uv...
uv python install
if errorlevel 1 (
  echo [setup] Could not install Python. Need a network connection and Python 3.11+.
  goto :fail
)

if not exist "%VENV_PY%" (
  echo [setup] Creating .venv with uv...
  uv venv .venv
  if errorlevel 1 (
    echo [setup] uv venv failed.
    goto :fail
  )
) else (
  echo [setup] Using existing .venv
)

echo [setup] Installing dependencies into .venv...
uv sync --all-groups --python "%VENV_PY%"
if errorlevel 1 (
  echo [setup] Dependency install failed. Check the messages above and try again.
  goto :fail
)

if not exist "%VENV_PY%" (
  echo [setup] .venv\Scripts\python.exe missing after sync.
  goto :fail
)

if not exist ".env" if exist ".env.example" (
  copy /Y ".env.example" ".env" >nul
  echo [setup] Created .env from .env.example. Add cloud keys there only if you need them.
  echo         CSV/Excel ingest works with no keys. Do not commit .env.
)

if not exist "data" mkdir data

echo.
echo [setup] Ready. Starting Streamlit with .venv\Scripts\python.exe ...
echo.

"%VENV_PY%" -m streamlit run streamlit_app.py --server.headless true --server.address localhost
if errorlevel 1 goto :fail
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
