@echo off
chcp 65001 >nul
cd /d "%~dp0"
python web_ui\app.py
pause
