# AMEVA Benchmark Suite 실행 스크립트

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
