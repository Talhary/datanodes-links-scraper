@echo off
setlocal enabledelayedexpansion
title DataNodes Link Extractor Pro

echo ===================================================
echo     DataNodes Link Extractor Pro - Local Launcher
echo ===================================================
echo.

:: Change working directory to script location
cd /d "%~dp0"

:: 1. Check Python installation
where python >nul 2>nul
if errorlevel 1 (
    echo [*] Python not detected. Attempting automatic installation...
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo [*] Installing Python via winget...
        winget install --id Python.Python.3.11 --exact --accept-package-agreements --accept-source-agreements -e --silent
    )
    where python >nul 2>nul
    if errorlevel 1 (
        echo [*] Downloading and installing Python via PowerShell...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$progressPreference = 'SilentlyContinue'; Write-Host '[*] Downloading Python installer...'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '$env:TEMP\python_installer.exe'; Write-Host '[*] Installing Python...'; Start-Process '$env:TEMP\python_installer.exe' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0' -Wait; Remove-Item '$env:TEMP\python_installer.exe' -ErrorAction SilentlyContinue"
    )
    :: Reload PATH from registry
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
    set "PATH=!USER_PATH!;!SYS_PATH!;!PATH!"
    
    where python >nul 2>nul
    if errorlevel 1 (
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;!PATH!"
        ) else if exist "%ProgramFiles%\Python311\python.exe" (
            set "PATH=%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;!PATH!"
        )
    )
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python installation could not be completed automatically.
        echo Please manually install Python from https://www.python.org and add it to your PATH.
        pause
        exit /b 1
    )
    echo [OK] Python is installed and configured.
)

:: 2. Check Node.js installation
where node >nul 2>nul
if errorlevel 1 (
    echo [*] Node.js not detected. Attempting automatic installation...
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo [*] Installing Node.js via winget...
        winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements -e --silent
    )
    where node >nul 2>nul
    if errorlevel 1 (
        echo [*] Downloading and installing Node.js via PowerShell...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$progressPreference = 'SilentlyContinue'; Write-Host '[*] Downloading Node.js installer...'; Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi' -OutFile '$env:TEMP\nodejs_installer.msi'; Write-Host '[*] Installing Node.js...'; Start-Process msiexec.exe -ArgumentList '/i $env:TEMP\nodejs_installer.msi /qn' -Wait; Remove-Item '$env:TEMP\nodejs_installer.msi' -ErrorAction SilentlyContinue"
    )
    :: Reload PATH from registry
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
    set "PATH=!USER_PATH!;!SYS_PATH!;!PATH!"
    
    where node >nul 2>nul
    if errorlevel 1 (
        if exist "%ProgramFiles%\nodejs\node.exe" (
            set "PATH=%ProgramFiles%\nodejs;%APPDATA%\npm;!PATH!"
        )
    )
    where node >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Node.js installation could not be completed automatically.
        echo Please manually install Node.js from https://nodejs.org and add it to your PATH.
        pause
        exit /b 1
    )
    echo [OK] Node.js is installed and configured.
)

:: 3. Setup Virtual Environment
set "VENV_DIR="
if exist "venv\Scripts\activate.bat" (
    set "VENV_DIR=venv"
) else if exist ".venv\Scripts\activate.bat" (
    set "VENV_DIR=.venv"
) else (
    echo [*] Virtual environment not found. Creating venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    set "VENV_DIR=venv"
)

echo [*] Activating virtual environment %VENV_DIR%...
call "%VENV_DIR%\Scripts\activate.bat"

:: 4. Install/Check Python Dependencies
echo [*] Checking Python dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt --upgrade-strategy only-if-needed --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies from requirements.txt.
        pause
        exit /b 1
    )
)

:: 5. Install/Check Node Dependencies
if not exist "node_modules" (
    echo [*] Installing Node.js dependencies puppeteer-core...
    call npm install --omit=dev
    if errorlevel 1 (
        echo [ERROR] Failed to install npm dependencies.
        pause
        exit /b 1
    )
)

echo.
echo ===================================================
echo   Starting DataNodes Web UI: http://localhost:8000
echo ===================================================
echo.

:: Open browser automatically after a short delay in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: 6. Launch FastAPI Server
python server.py

pause
