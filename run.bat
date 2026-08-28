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
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: 2. Check Node.js installation
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js v18+ from nodejs.org to run Puppeteer worker.
    pause
    exit /b 1
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
