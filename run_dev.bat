@echo off
title MailerX Pro - Development Mode
color 0E

echo.
echo ========================================
echo   MailerX Pro - Development Mode
echo ========================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install flask flask-cors pywebview
)

:: Create data directories
if not exist "data\templates" mkdir data\templates
if not exist "data\attachments" mkdir data\attachments
if not exist "data\uploads" mkdir data\uploads

echo.
echo Starting MailerX Pro in development mode...
echo.
python desktop_app.py

pause