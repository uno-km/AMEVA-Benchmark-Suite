@echo off
setlocal enabledelayedexpansion
:: [중요] UTF-8 환경으로 강제 전환 (Matrix 콘솔 글깨짐 방지)
chcp 65001 >nul
title AMEVA-Bench v5.0 [The Architect's Protocol]

:: 작업 디렉토리를 배치 파일 위치로 강제 고정 (상대 경로 버그 원천 차단)
cd /d "%~dp0"

set "REPORT_FILE=AMEVA_Setup_Report.log"
set "DOCKER_STATUS=Unknown"
set "DOCKER_VER=None"
set "DOCKER_PATH=Not Found"
set "MODEL_QWEN=Missing"
set "MODEL_LLAMA=Missing"
set "CPU_ACCEL=Checking..."
set "GPU_STATUS=Not Found / CPU Only Mode"

echo ==========================================
echo       AMEVA-Bench: Singularity Ignition
echo       "Welcome back, Architect."
echo ==========================================
echo.

:: [1] Hardware & Daemon Check (우리의 노하우 1: GPU 전력 측정기 사전 탐지)
echo [1/4] Checking Hardware & Docker Engine...
nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    set "GPU_STATUS=NVIDIA GPU Detected (Tokens/Joule Tracking: ONLINE)"
)

:: 단순 설치 여부가 아니라 '데몬(백그라운드 서비스)'이 살아있는지 확인
docker info >nul 2>&1
if %errorlevel% equ 0 (
    set "DOCKER_STATUS=Engine is Running & Ready"
) else (
    docker --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "DOCKER_STATUS=Installed but Engine is SLEEPING (Please start Docker Desktop)"
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
echo [2/4] Checking Assets: LLM Edge Models...
if not exist "models" mkdir models
powershell -NoProfile -ExecutionPolicy Bypass -Command "$check = Test-NetConnection huggingface.co -Port 443 -InformationLevel Quiet; if (-not $check) { Write-Host '[Warning] Firewall detected. Auto-download might fail.' -ForegroundColor Yellow }"

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ModelDir = '.\models'; $files = @{ 'qwen2.5-0.5b.gguf'='https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q8_0.gguf'; 'llama3.2-1b.gguf'='https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf' }; foreach($f in $files.Keys) { if(-not (Test-Path \"$ModelDir\$f\")) { curl.exe -k -L $files[$f] -o \"$ModelDir\$f\" } }"

if exist "models\qwen2.5-0.5b.gguf" set "MODEL_QWEN=Success"
if exist "models\llama3.2-1b.gguf" set "MODEL_LLAMA=Success"

:: [3] CPU Accel Check
powershell -NoProfile -ExecutionPolicy Bypass -Command "$feat = (Get-CimInstance Win32_Processor).Caption; if ($feat -match 'AVX2') { $accel='AVX2 Optimized' } else { $accel='Standard' }; Set-Content -Path 'cpu_tmp.txt' -Value $accel"
set /p CPU_ACCEL=<cpu_tmp.txt
del cpu_tmp.txt

:: [4] Python & Report
echo.
echo [3/4] Software Environment: Python Virtual Sandbox
if not exist "venv\Scripts\activate.bat" (
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt >nul 2>&1

:: Report Generation
echo ========================================== > %REPORT_FILE%
echo        AMEVA SINGULARITY DEPLOYMENT REPORT   >> %REPORT_FILE%
echo        Timestamp: %date% %time%           >> %REPORT_FILE%
echo ========================================== >> %REPORT_FILE%
echo [SYSTEM INFO] >> %REPORT_FILE%
echo GPU Power Track: %GPU_STATUS% >> %REPORT_FILE%
echo Docker Status  : %DOCKER_STATUS% >> %REPORT_FILE%
echo Docker Version : %DOCKER_VER% >> %REPORT_FILE%
echo Docker Path    : %DOCKER_PATH% >> %REPORT_FILE%
echo CPU Accel      : %CPU_ACCEL% >> %REPORT_FILE%
echo. >> %REPORT_FILE%
echo [MODELS] >> %REPORT_FILE%
echo Qwen-2.5-0.5B  : %MODEL_QWEN% >> %REPORT_FILE%
echo Llama-3.2-1B   : %MODEL_LLAMA% >> %REPORT_FILE%
echo. >> %REPORT_FILE%
echo [LIBRARIES] >> %REPORT_FILE%
pip list >> %REPORT_FILE%
echo ========================================== >> %REPORT_FILE%

type %REPORT_FILE%
echo.
echo [4/4] Igniting AMEVA Matrix Core...

:: ======================================================================
:: 아키텍트의 노하우 주입 섹션 (Ignition Core)
:: ======================================================================
set "VENV_BASE=%~dp0venv"
set "PYSIDE_PATH=%VENV_BASE%\Lib\site-packages\PySide6"

:: 1. 시스템 환경 변수 최우선화 (Qt 플러그인 충돌 방지)
set "PATH=%VENV_BASE%\Scripts;%PYSIDE_PATH%;%PYSIDE_PATH%\plugins;%PATH%"
set "QT_QPA_PLATFORM_PLUGIN_PATH=%PYSIDE_PATH%\plugins\platforms"
set "PYTHONPATH=%~dp0src"

:: 2. 파이썬 버퍼링 제거 (UI 콘솔에 시스템 로그가 실시간으로 꽂히도록 강제)
set "PYTHONUNBUFFERED=1"

:: 3. GUI가 알 수 없는 이유로 튕길 때 원인을 보기 위한 비상 디버그 스위치 (필요시 주석 해제)
:: set "QT_DEBUG_PLUGINS=1"

:: 실행!
python src\main.py

:: 실행 종료 후 안전한 자원 해제
deactivate
echo.
echo [SYSTEM] Matrix interface disconnected.
pause