@echo off
title Tomato Novel Downloader

echo ========================================
echo      Tomato Novel Downloader v1.0
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found!
    echo Please install Python 3.8 or higher
    echo.
    pause
    exit /b 1
)

echo Checking dependencies...
echo.

REM Check and install dependencies
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies!
        pause
        exit /b 1
    )
) else (
    echo Dependencies already installed
)

echo.
echo ========================================
echo  Starting Tomato Novel Downloader...
echo ========================================
echo.

REM Start GUI
python gui.py

pause