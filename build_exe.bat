@echo off
title MailerX Pro - Complete Builder
color 0A

:: ========================================
:: MailerX Pro - Desktop Executable Builder
:: Combined and Improved Version
:: ========================================

setlocal enabledelayedexpansion

:: Check for Administrator privileges (optional)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Not running as Administrator
    echo [INFO] Some features may require admin rights
    echo.
)

:menu
cls
echo.
echo ========================================
echo    MailerX Pro - Build System
echo ========================================
echo.
echo   [1] Full Build (Clean + Install + Build)
echo   [2] Quick Build (Skip Clean)
echo   [3] Install Dependencies Only
echo   [4] Clean Build Files Only
echo   [5] Test Application (Development Mode)
echo   [6] Exit
echo.
echo ========================================
set /p choice="Select option (1-6): "

if "%choice%"=="1" goto full_build
if "%choice%"=="2" goto quick_build
if "%choice%"=="3" goto install_deps
if "%choice%"=="4" goto clean_only
if "%choice%"=="5" goto test_app
if "%choice%"=="6" goto exit
goto menu

:full_build
cls
echo.
echo ========================================
echo   FULL BUILD - Clean + Install + Build
echo ========================================
echo.
goto clean_build

:quick_build
cls
echo.
echo ========================================
echo   QUICK BUILD - Skip Clean
echo ========================================
echo.
goto start_build

:install_deps
cls
echo.
echo ========================================
echo   Installing Dependencies Only
echo ========================================
echo.
goto install_packages

:clean_only
cls
echo.
echo ========================================
echo   Cleaning Build Files
echo ========================================
echo.
goto clean_files

:test_app
cls
echo.
echo ========================================
echo   Testing Application
echo ========================================
echo.
goto run_dev

:clean_build
echo.
echo [1/5] Cleaning previous builds...
echo.

:: Clean build directories
if exist "build" (
    echo Removing build directory...
    rmdir /s /q build 2>nul
)
if exist "dist" (
    echo Removing dist directory...
    rmdir /s /q dist 2>nul
)
if exist "__pycache__" (
    echo Removing __pycache__...
    rmdir /s /q __pycache__ 2>nul
)

:: Clean spec files
if exist "*.spec" (
    echo Removing spec files...
    del /q *.spec 2>nul
)

echo [OK] Cleanup complete
echo.

:start_build
:: Check Python installation
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    goto menu
)

echo [OK] Python found:
python --version
echo.

:install_packages
:: Install required packages
echo [2/5] Installing required packages...
echo.

:: Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

:: Install packages
echo Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [WARNING] PyInstaller install had issues, continuing...
)

echo Installing Flask and dependencies...
pip install flask flask-cors pywebview --quiet
if errorlevel 1 (
    echo [WARNING] Package install had issues, continuing...
)

echo.
echo [OK] Package installation complete
echo.

:: Create data directories
echo [3/5] Creating data directories...

:: Create directory structure
if not exist "data" mkdir data 2>nul
if not exist "data\templates" mkdir data\templates 2>nul
if not exist "data\attachments" mkdir data\attachments 2>nul
if not exist "data\uploads" mkdir data\uploads 2>nul
if not exist "data\logs" mkdir data\logs 2>nul
if not exist "data\backups" mkdir data\backups 2>nul

echo [OK] Data directories created
echo.

:: Check required files
echo [4/5] Checking required files...

set missing_files=0
if not exist "desktop_app.py" (
    echo [ERROR] Missing: desktop_app.py
    set /a missing_files+=1
)
if not exist "main.py" (
    echo [ERROR] Missing: main.py
    set /a missing_files+=1
)
if not exist "index.html" (
    echo [ERROR] Missing: index.html
    set /a missing_files+=1
)

if %missing_files% gtr 0 (
    echo.
    echo [ERROR] Missing %missing_files% required file(s)
    echo Please ensure all files are present
    echo.
    pause
    goto menu
)

echo [OK] All required files present
echo.

:: Build executable
echo [5/5] Building executable...
echo This may take 2-5 minutes depending on your system...
echo.

:: Use direct PyInstaller command for better compatibility
pyinstaller --onefile --windowed --name=MailerXPro ^
    --add-data "index.html;." ^
    --add-data "main.py;." ^
    --add-data "data;data" ^
    --hidden-import flask ^
    --hidden-import flask_cors ^
    --hidden-import werkzeug ^
    --hidden-import jinja2 ^
    --hidden-import email ^
    --hidden-import smtplib ^
    --hidden-import csv ^
    --hidden-import json ^
    --hidden-import uuid ^
    --hidden-import threading ^
    --hidden-import datetime ^
    --hidden-import logging ^
    --hidden-import webbrowser ^
    --hidden-import socket ^
    --hidden-import platform ^
    --hidden-import mimetypes ^
    --collect-all flask ^
    --collect-all flask_cors ^
    --collect-all werkzeug ^
    --collect-all jinja2 ^
    --noupx ^
    desktop_app.py

:: Check build result
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo        BUILD FAILED!
    echo ========================================
    echo.
    echo Possible issues:
    echo 1. Missing Python packages
    echo 2. PyInstaller configuration error
    echo 3. File permission issues
    echo.
    echo Try running as Administrator or
    echo select option 5 to test in development mode
    echo.
    pause
    goto menu
)

:: Verify build success
if exist "dist\MailerXPro.exe" (
    echo.
    echo ========================================
    echo      BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Executable: %cd%\dist\MailerXPro.exe
    echo.
    
    :: Get file size
    for %%A in ("dist\MailerXPro.exe") do (
        set size=%%~zA
        set /a size_mb=!size!/1048576
        echo Size: ~!size_mb! MB
    )
    echo.
    echo ========================================
    echo.
    
    :: Offer to run
    echo Options:
    echo   [Y] Run MailerXPro now
    echo   [N] Open dist folder
    echo   [C] Return to menu
    echo.
    set /p run_choice="Choice (Y/N/C): "
    
    if /i "!run_choice!"=="Y" (
        echo.
        echo Launching MailerXPro...
        start "" "dist\MailerXPro.exe"
        echo.
        echo Application is starting. Please wait 5-10 seconds...
    ) else if /i "!run_choice!"=="N" (
        echo.
        echo Opening dist folder...
        start explorer "%cd%\dist"
    )
) else (
    echo.
    echo ========================================
    echo        BUILD FAILED!
    echo ========================================
    echo.
    echo Executable not found in dist folder
    echo.
    echo Trying alternative build method...
    echo.
    
    :: Alternative build method (without windowed mode for debugging)
    echo Building with console for debugging...
    pyinstaller --onefile --name=MailerXPro_debug ^
        --add-data "index.html;." ^
        --add-data "main.py;." ^
        --add-data "data;data" ^
        desktop_app.py
    
    if exist "dist\MailerXPro_debug.exe" (
        echo.
        echo [INFO] Debug version created: dist\MailerXPro_debug.exe
        echo [INFO] Run this to see error messages
    )
)

echo.
pause
goto menu

:clean_files
cls
echo.
echo Cleaning build files...
echo.

:: Clean build directories
if exist "build" (
    echo Removing build directory...
    rmdir /s /q build 2>nul
    echo [OK] Removed build/
)

if exist "dist" (
    echo Removing dist directory...
    rmdir /s /q dist 2>nul
    echo [OK] Removed dist/
)

if exist "__pycache__" (
    echo Removing __pycache__...
    rmdir /s /q __pycache__ 2>nul
    echo [OK] Removed __pycache__/
)

:: Clean spec files
if exist "*.spec" (
    echo Removing spec files...
    del /q *.spec 2>nul
    echo [OK] Removed spec files
)

:: Clean PyInstaller cache
if exist "%USERPROFILE%\AppData\Local\pyinstaller" (
    echo Cleaning PyInstaller cache...
    rmdir /s /q "%USERPROFILE%\AppData\Local\pyinstaller" 2>nul
)

echo.
echo ========================================
echo   CLEANUP COMPLETE!
echo ========================================
echo.
echo Disk space freed
echo.
pause
goto menu

:run_dev
cls
echo.
echo ========================================
echo   Development Mode (No Build Required)
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    goto menu
)

:: Install dependencies if needed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install flask flask-cors pywebview --quiet
)

:: Create data directories
if not exist "data\templates" mkdir data\templates 2>nul
if not exist "data\attachments" mkdir data\attachments 2>nul
if not exist "data\uploads" mkdir data\uploads 2>nul

echo.
echo Starting MailerX Pro in development mode...
echo.
echo [INFO] The application will open in a new window
echo [INFO] Close the window to stop the application
echo [INFO] Press Ctrl+C in this window to force stop
echo.

:: Run the desktop app
python desktop_app.py

echo.
echo Application stopped
echo.
pause
goto menu

:exit
cls
echo.
echo ========================================
echo   Thank you for using MailerX Pro!
echo ========================================
echo.
exit /b 0