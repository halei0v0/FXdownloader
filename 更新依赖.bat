@echo off
title Update Dependencies

echo ========================================
echo      Update Dependencies
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found!
    pause
    exit /b 1
)

echo Updating dependencies...
echo.

pip install --upgrade -r requirements.txt

if errorlevel 1 (
    echo.
    echo Error: Failed to update dependencies!
) else (
    echo.
    echo Dependencies updated successfully!
)

echo.
pause