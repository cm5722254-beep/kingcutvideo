@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo    King Video Cutter (Sdech Kat Video)
echo    Starting application, please wait...
echo ======================================================
echo.

set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PY_EXE=venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10+ and make sure to check 'Add python.exe to PATH'.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

"%PY_EXE%" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%.
    pause
)
