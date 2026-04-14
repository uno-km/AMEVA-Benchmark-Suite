@echo off
setlocal enabledelayedexpansion
:: [중요] UTF-8 환경으로 강제 전환
chcp 65001 >nul
title AMEVA-Bench Ultimate Launcher & Reporter

set "REPORT_FILE=AMEVA_Setup_Report.log"
set "DOCKER_STATUS=Unknown"
set "DOCKER_VER=None"
set "DOCKER_PATH=Not Found"
set "MODEL_QWEN=Missing"
set "MODEL_LLAMA=Missing"
set "CPU_ACCEL=Checking..."

echo ==========================================
echo      AMEVA-Bench: Singularity Ignition
echo ==========================================
echo.

:: [1] Docker Check
echo [1/4] Checking System: Docker...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    set "DOCKER_STATUS=Already Installed"
) else (
    set "PATH=%PATH%;C:\Program Files\Docker\Docker\resources\bin"
    docker --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "DOCKER_STATUS=Found via Path Injection"
    ) else (
        set "DOCKER_STATUS=Newly Installed"
        echo [Info] Starting Docker Installation...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe' -OutFile \"$env:TEMP\DockerInstaller.exe\"; Start-Process -Wait -FilePath \"$env:TEMP\DockerInstaller.exe\" -ArgumentList 'install', '--quiet', '--accept-license', '--backend=wsl-2'; Remove-Item \"$env:TEMP\DockerInstaller.exe\""
        set "DOCKER_VER=Latest (Reboot Required)"
    )
)

if "!DOCKER_VER!"=="None" (
    for /f "tokens=*" %%i in ('docker --version') do set "DOCKER_VER=%%i"
    for /f "tokens=*" %%i in ('where docker') do set "DOCKER_PATH=%%i"
)

:: [2] Assets & Firewall
echo.
echo [2/4] Checking Assets: Models...
if not exist "models" mkdir models
powershell -NoProfile -ExecutionPolicy Bypass -Command "$check = Test-NetConnection huggingface.co -Port 443 -InformationLevel Quiet; if (-not $check) { Write-Host '![Notice] Firewall detected. Auto-download might fail.' -ForegroundColor Yellow }"

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ModelDir = '.\models'; $files = @{ 'qwen2.5-0.5b.gguf'='https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q8_0.gguf'; 'llama3.2-1b.gguf'='https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf' }; foreach($f in $files.Keys) { if(-not (Test-Path \"$ModelDir\$f\")) { curl.exe -k -L $files[$f] -o \"$ModelDir\$f\" } }"

if exist "models\qwen2.5-0.5b.gguf" set "MODEL_QWEN=Success"
if exist "models\llama3.2-1b.gguf" set "MODEL_LLAMA=Success"

:: [3] CPU Accel Check
powershell -NoProfile -ExecutionPolicy Bypass -Command "$feat = (Get-CimInstance Win32_Processor).Caption; if ($feat -match 'AVX2') { $accel='AVX2 Optimized' } else { $accel='Standard' }; Set-Content -Path 'cpu_tmp.txt' -Value $accel"
set /p CPU_ACCEL=<cpu_tmp.txt
del cpu_tmp.txt

:: [4] Python & Report
echo.
echo [3/4] Software Environment: Python venv
if not exist "venv\Scripts\activate.bat" (
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt >nul 2>&1

echo ========================================== > %REPORT_FILE%
echo        AMEVA SETUP DEPLOYMENT REPORT       >> %REPORT_FILE%
echo        Timestamp: %date% %time%           >> %REPORT_FILE%
echo ========================================== >> %REPORT_FILE%
echo [SYSTEM INFO] >> %REPORT_FILE%
echo Docker Status: %DOCKER_STATUS% >> %REPORT_FILE%
echo Docker Version: %DOCKER_VER% >> %REPORT_FILE%
echo Docker Path: %DOCKER_PATH% >> %REPORT_FILE%
echo CPU Acceleration: %CPU_ACCEL% >> %REPORT_FILE%
echo. >> %REPORT_FILE%
echo [MODELS] >> %REPORT_FILE%
echo Qwen-2.5-0.5B: %MODEL_QWEN% >> %REPORT_FILE%
echo Llama-3.2-1B: %MODEL_LLAMA% >> %REPORT_FILE%
echo. >> %REPORT_FILE%
echo [LIBRARIES] >> %REPORT_FILE%
pip list >> %REPORT_FILE%
echo ========================================== >> %REPORT_FILE%

type %REPORT_FILE%
echo.
echo [4/4] Igniting AMEVA Architecture...
:: 런처 하단 Ignition 섹션
set "VENV_BASE=%~dp0venv"
set "PYSIDE_PATH=%VENV_BASE%\Lib\site-packages\PySide6"
:: 시스템 경로보다 가상환경 경로를 최우선으로!
set "PATH=%VENV_BASE%\Scripts;%PYSIDE_PATH%;%PYSIDE_PATH%\plugins;%PATH%"
set "QT_QPA_PLATFORM_PLUGIN_PATH=%PYSIDE_PATH%\plugins\platforms"
set "PYTHONPATH=%~dp0src"


python src\main.py




deactivate
pause