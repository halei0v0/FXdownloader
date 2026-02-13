@echo off
title Build FXdownloader

echo ========================================
echo      Build FXdownloader to EXE
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

REM Check PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo Error: Failed to install PyInstaller!
        pause
        exit /b 1
    )
)

echo Cleaning old build files...
if exist "build" (
    rmdir /s /q "build"
)
if exist "dist" (
    rmdir /s /q "dist"
)
echo.

echo ========================================
echo  Starting build process...
echo ========================================
echo.

REM Build EXE
pyinstaller FXdownloader.spec

if errorlevel 1 (
    echo.
    echo Error: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build completed successfully!
echo ========================================
echo.
echo The EXE file is located in: dist\FXdownloader.exe
echo.
pause