# AMEVA Benchmark Suite 실행 스크립트

# [1] Ollama 상태 확인 및 기동
Write-Host "Ollama 서비스 상태 점검 중..." -ForegroundColor Cyan
$ollamaPort = 11434
$ollamaCheck = Test-NetConnection -ComputerName "127.0.0.1" -Port $ollamaPort -WarningAction SilentlyContinue
if (-not $ollamaCheck.TcpTestSucceeded) {
    Write-Host "Ollama가 켜져 있지 않습니다. Ollama 앱을 실행합니다..." -ForegroundColor Yellow
    $ollamaPath = "C:\Users\ATSAdmin\AppData\Local\Programs\Ollama\ollama app.exe"
    if (Test-Path $ollamaPath) {
        Start-Process -FilePath $ollamaPath
        Write-Host "Ollama 초기화 대기 중 (5초)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    } else {
        Write-Host "[경고] Ollama 앱을 찾을 수 없습니다. 경로: $ollamaPath" -ForegroundColor Red
    }
} else {
    Write-Host "Ollama 서비스: ONLINE" -ForegroundColor Green
}

# [2] Docker 상태 확인 및 기동
Write-Host "Docker Engine 상태 점검 중..." -ForegroundColor Cyan
& docker info >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker가 실행 중이 아닙니다. Docker Desktop을 실행합니다..." -ForegroundColor Yellow
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerPath) {
        Start-Process -FilePath $dockerPath
        Write-Host "Docker Engine이 켜질 때까지 대기합니다. (최대 30초)..." -ForegroundColor Yellow
        $timeout = 30
        while ($timeout -gt 0) {
            Start-Sleep -Seconds 3
            & docker info >$null 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
                break
            }
            $timeout -= 3
            Write-Host "대기 중... ($timeout 초 남음)" -ForegroundColor Gray
        }
        if ($timeout -le 0) {
            Write-Host "[경고] Docker Engine 기동이 지연되고 있습니다. 백그라운드에서 실행을 계속 시도합니다." -ForegroundColor Red
        }
    } else {
        Write-Host "[경고] Docker Desktop을 찾을 수 없습니다. 경로: $dockerPath" -ForegroundColor Red
    }
} else {
    Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
}

# 1. 가상 환경이 없으면 생성합니다.
if (-not (Test-Path -Path ".\venv")) {
    Write-Host "가상 환경(venv)을 생성하는 중..." -ForegroundColor Cyan
    python -m venv venv
}

# 2. 가상 환경을 활성화합니다.
Write-Host "가상 환경을 활성화하는 중..." -ForegroundColor Cyan
. .\venv\Scripts\Activate.ps1

# 3. 환경 진단 및 프로그램 실행을 위해 launch.bat을 호출합니다.
Write-Host "AMEVA Benchmark Suite를 실행합니다..." -ForegroundColor Cyan
cmd.exe /c launch.bat
