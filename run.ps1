# AMEVA Benchmark Suite 실행 및 환경 진단 스크립트

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ($ScriptPath) { Set-Location -Path $ScriptPath }

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($PSVersionTable.PSVersion.Major -le 5) { chcp 65001 | Out-Null }
$ErrorActionPreference = "Stop"

Write-Host "--- AMEVA Benchmark Suite Environment Setup ---" -ForegroundColor Cyan
Write-Host "Path: $(Get-Location)" -ForegroundColor Gray

# [1] Ollama 상태 확인 및 자동 기동
Write-Host "Checking Ollama service status..." -ForegroundColor Cyan
$ollamaPort = 11434
$ollamaCheck = Test-NetConnection -ComputerName "127.0.0.1" -Port $ollamaPort -WarningAction SilentlyContinue

if (-not $ollamaCheck.TcpTestSucceeded) {
    Write-Host "Ollama is not running. Launching Ollama app..." -ForegroundColor Yellow
    $ollamaPath = "$env:LocalAppData\Programs\Ollama\ollama app.exe"
    
    if (Test-Path $ollamaPath) {
        Start-Process -FilePath $ollamaPath
        Write-Host "Waiting for Ollama initialization (5s)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    } else {
        Write-Host "[WARNING] Ollama app not found. Path: $ollamaPath" -ForegroundColor Red
    }
} else {
    Write-Host "Ollama service: ONLINE" -ForegroundColor Green
}

# [2] Docker 데몬 상태 확인 및 자동 기동
Write-Host "Checking Docker Engine status..." -ForegroundColor Cyan
& docker info >$null 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Launching Docker Desktop..." -ForegroundColor Yellow
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    
    if (Test-Path $dockerPath) {
        Start-Process -FilePath $dockerPath
        Write-Host "Waiting for Docker Engine to start (max 30s)..." -ForegroundColor Yellow
        $timeout = 30
        while ($timeout -gt 0) {
            Start-Sleep -Seconds 3
            & docker info >$null 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
                break
            }
            $timeout -= 3
            Write-Host "Waiting... ($timeout seconds left)" -ForegroundColor Gray
        }
        if ($timeout -le 0) {
            Write-Host "[WARNING] Docker Engine startup is delayed. Continuing in background." -ForegroundColor Red
        }
    } else {
        Write-Host "[WARNING] Docker Desktop not found. Path: $dockerPath" -ForegroundColor Red
    }
} else {
    Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
}

# [3] 가상환경 및 의존성 검증 단계
$EnvDir = ".\venv"
$VenvValid = (Test-Path -Path "$EnvDir\Scripts\python.exe") -and (Test-Path -Path "$EnvDir\Scripts\Activate.ps1")

if (-not $VenvValid) {
    if (Test-Path -Path $EnvDir) {
        Write-Host "Incomplete or corrupted virtual environment found. Recreating..." -ForegroundColor Yellow
        Remove-Item -Path $EnvDir -Force -Recurse -ErrorAction SilentlyContinue
    }
    Write-Host "Virtual environment (venv) not found. Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $EnvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
    
    Write-Host "Upgrading pip and installing requirements..." -ForegroundColor Yellow
    & "$EnvDir\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
    & "$EnvDir\Scripts\python.exe" -m pip install -r requirements.txt
}

# [4] 모델 저장 폴더 확인 및 모델 확인
$ModelDir = "c:\ameva\models\llm"
$AltSrc = "c:\ameva\llm"
if (-not (Test-Path $ModelDir)) {
    New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
}

$files = @{
    "qwen2.5-1.5b-instruct-q4_k_m.gguf" = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    "Llama-3.2-1B-Instruct-Q4_K_M.gguf" = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
}

foreach ($f in $files.Keys) {
    $destFile = Join-Path $ModelDir $f
    if (-not (Test-Path $destFile)) {
        $altFile = Join-Path $AltSrc $f
        if (Test-Path $altFile) {
            Write-Host "Copying $f from local backup..." -ForegroundColor Green
            Copy-Item $altFile $destFile
        } else {
            Write-Host "Downloading $f from Hugging Face..." -ForegroundColor Green
            try {
                Invoke-WebRequest -Uri $files[$f] -OutFile $destFile -UseBasicParsing -TimeoutSec 1800
            } catch {
                Write-Host "[WARNING] Failed to download $f. Please place it manually in $ModelDir." -ForegroundColor Red
            }
        }
    }
}

# [5] 가상환경 활성화 및 가동
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. "$EnvDir\Scripts\Activate.ps1"

Write-Host "Launching AMEVA Benchmark Suite Matrix Core..." -ForegroundColor Cyan
$env:PYTHONPATH = "$ScriptPath\src"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

& "$EnvDir\Scripts\python.exe" src\app_launcher.py
