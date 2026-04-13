@echo off
chcp 65001 >nul
title AMEVA-Bench All-in-One Launcher

echo ==========================================
echo     ?? AMEVA-Bench: Singularity System Ignition
echo ==========================================
echo.

:: [1] Check Docker installation and install automatically if missing
echo [1/4] System Environment Check: Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Warning] Docker not detected! Starting automatic installation...
    echo (Administrator privileges may be required, and a PC reboot is required after installation.)
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '?? Downloading Docker Desktop...' -ForegroundColor Cyan; Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe' -OutFile \"$env:TEMP\DockerInstaller.exe\"; Write-Host '?? Running silent installation (This may take a few minutes)...' -ForegroundColor Yellow; Start-Process -Wait -FilePath \"$env:TEMP\DockerInstaller.exe\" -ArgumentList 'install', '--quiet', '--accept-license', '--backend=wsl-2'; Remove-Item \"$env:TEMP\DockerInstaller.exe\"; Write-Host '[Success] Installation complete! Please reboot your PC and run this script again.' -ForegroundColor Green"
    pause
    exit
) else (
    echo [Success] Docker engine detected.
)

:: [2] Download HuggingFace models
echo.
echo [2/4] Asset Check: HuggingFace Model Data
if not exist "models" mkdir models
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ModelDir = '.\models'; $files = @{ 'qwen2.5-0.5b.gguf'='https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q8_0.gguf'; 'llama3.2-1b.gguf'='https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf' }; foreach($f in $files.Keys) { if(-not (Test-Path \"$ModelDir\$f\")) { Write-Host \"?? Downloading $f...\" -ForegroundColor Cyan; curl.exe -L $files[$f] -o \"$ModelDir\$f\" } else { Write-Host \"[Success] $f already exists.\" -ForegroundColor Green } }"

:: [3] Python Virtual Environment Setup
echo.
echo [3/4] Software Environment Setup: Python venv
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
echo Installing dependency packages...
pip install -r requirements.txt

:: [4] Architecture Ignition
echo.
echo [4/4] Igniting AMEVA Architecture!
set PYTHONPATH=%~dp0src
python src/main.py

deactivate
pause