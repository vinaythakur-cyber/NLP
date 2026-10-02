@echo off
rem lingua-bridge launcher for Windows.
rem   run.bat            full install (translation + web UI), then start the app
rem   run.bat --light    conversion + detection + web UI only (no PyTorch, installs in seconds)
rem   run.bat --reinstall   force a fresh install of the packages
setlocal enabledelayedexpansion
cd /d "%~dp0"

set LIGHT=0
set REINSTALL=0
for %%A in (%*) do (
  if /I "%%A"=="--light" set LIGHT=1
  if /I "%%A"=="--reinstall" set REINSTALL=1
)

set PY=
for %%V in (3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set PY=py -%%V
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set PY=python
)
if not defined PY (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/
  echo During setup, tick "Add python.exe to PATH". Then run this file again.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not create the virtual environment. & pause & exit /b 1 )
)
call .venv\Scripts\activate.bat

set MODE=full
set EXTRAS=api,translate
if "%LIGHT%"=="1" ( set MODE=light & set EXTRAS=api )
set STAMP=.venv\.lingua-installed-%MODE%
if "%REINSTALL%"=="1" del "%STAMP%" >nul 2>&1
if not exist "%STAMP%" (
  echo Installing lingua-bridge[%EXTRAS%] ^(the full install downloads PyTorch, a few GB, one time^)...
  python -m pip install --quiet --upgrade pip
  python -m pip install -e ".[%EXTRAS%]"
  if errorlevel 1 ( echo Installation failed. See the messages above. & pause & exit /b 1 )
  if not "%LIGHT%"=="1" python scripts\setup_torch_gpu.py
  echo done> "%STAMP%"
)

if not exist .env copy .env.example .env >nul
echo.
lingua doctor
echo.
lingua serve --open
pause
