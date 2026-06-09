# AMEVA Benchmark Suite 실행 및 환경 진단 스크립트

# [1] Ollama 상태 확인 및 필요시 자동 기동 단계
# 로컬 포트 11434를 테스트하여 Ollama 서비스가 기동되어 있는지 점검합니다.
Write-Host "Checking Ollama service status..." -ForegroundColor Cyan
$ollamaPort = 11434
$ollamaCheck = Test-NetConnection -ComputerName "127.0.0.1" -Port $ollamaPort -WarningAction SilentlyContinue

# 만약 11434 포트 접속이 실패한다면 Ollama가 꺼져 있는 것으로 간주합니다.
if (-not $ollamaCheck.TcpTestSucceeded) {
    Write-Host "Ollama is not running. Launching Ollama app..." -ForegroundColor Yellow
    $ollamaPath = "C:\Users\ATSAdmin\AppData\Local\Programs\Ollama\ollama app.exe"
    
    # 지정한 로컬 경로에 Ollama 앱 실행 파일이 실재하는지 검증합니다.
    if (Test-Path $ollamaPath) {
        # Ollama 앱을 실행하여 트레이 아이콘 및 서버 데몬을 가동합니다.
        Start-Process -FilePath $ollamaPath
        # 앱이 켜지고 포트가 정상 활성화될 때까지 5초의 안전 버퍼 시간을 대기합니다.
        Write-Host "Waiting for Ollama initialization (5s)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    } else {
        # 앱 경로가 유효하지 않을 때 경고를 출력합니다.
        Write-Host "[Warning] Ollama app not found. Path: $ollamaPath" -ForegroundColor Red
    }
} else {
    # 이미 켜져 있다면 온라인 메시지를 표시하고 통과합니다.
    Write-Host "Ollama service: ONLINE" -ForegroundColor Green
}

# [2] Docker 데몬 상태 확인 및 필요시 자동 기동 단계
# docker info 명령어를 통해 호스트 백그라운드에 도커 엔진이 활성화되어 소통 가능한지 체크합니다.
Write-Host "Checking Docker Engine status..." -ForegroundColor Cyan
& docker info >$null 2>&1

# 이전 명령어의 종료 코드가 0이 아닌 경우 도커 엔진이 정지해 있는 것입니다.
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Launching Docker Desktop..." -ForegroundColor Yellow
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    
    # Docker Desktop 설치 경로가 정상적으로 존재하는지 탐색합니다.
    if (Test-Path $dockerPath) {
        # Docker Desktop 관리 런처를 실행합니다.
        Start-Process -FilePath $dockerPath
        # 엔진 기동은 무겁기 때문에 최대 30초 동안 3초 단위로 폴링 검증을 진행합니다.
        Write-Host "Waiting for Docker Engine to start (max 30s)..." -ForegroundColor Yellow
        $timeout = 30
        while ($timeout -gt 0) {
            Start-Sleep -Seconds 3
            & docker info >$null 2>&1
            # 기동 성공 시 루프를 즉시 이탈합니다.
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
                break
            }
            $timeout -= 3
            Write-Host "Waiting... ($timeout seconds left)" -ForegroundColor Gray
        }
        # 30초 대기 한계치에 도달할 때까지 도커가 안 켜지면 비동기 백그라운드 기동 상태로 전환합니다.
        if ($timeout -le 0) {
            Write-Host "[Warning] Docker Engine startup is delayed. Continuing in background." -ForegroundColor Red
        }
    } else {
        # Docker Desktop 실행 파일이 존재하지 않는 경우의 예외 메시지입니다.
        Write-Host "[Warning] Docker Desktop not found. Path: $dockerPath" -ForegroundColor Red
    }
} else {
    # 이미 도커 엔진이 켜져 작동 가능한 경우입니다.
    Write-Host "Docker Engine: ONLINE" -ForegroundColor Green
}

# [3] 파이썬 가상환경(venv) 검증 및 패키지 실행 단계
# 가상 환경 디렉토리가 부재할 시 신규 구축 프로세스를 밟습니다.
if (-not (Test-Path -Path ".\venv")) {
    Write-Host "Creating virtual environment (venv)..." -ForegroundColor Cyan
    python -m venv venv
}

# [4] 가상환경 활성화 단계
# PowerShell 세션 환경에 맞추어 활성화 스크립트를 도트 로딩합니다.
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. .\venv\Scripts\Activate.ps1

# [5] 메인 어플리케이션 진입 및 기동
# 최종적으로 환경 설정 리포트 및 의존성을 정돈하는 launch.bat을 호출하여 실행합니다.
Write-Host "Launching AMEVA Benchmark Suite..." -ForegroundColor Cyan
cmd.exe /c launch.bat
