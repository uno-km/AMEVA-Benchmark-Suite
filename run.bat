@echo off
chcp 65001 > nul
powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if %errorlevel% neq 0 (
    echo.
    echo System encountered an error. Press any key to close.
    pause
)
