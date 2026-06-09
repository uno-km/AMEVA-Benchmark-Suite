# AMEVA Benchmark Suite 실행 스크립트

# 1. 가상 환경이 없으면 생성합니다.
if (-not (Test-Path -Path ".\venv")) {
    Write-Host "가상 환경(venv)을 생성하는 중..." -ForegroundColor Cyan
    python -m venv venv
}

# 2. 가상 환경을 활성화합니다.
Write-Host "가상 환경을 활성화하는 중..." -ForegroundColor Cyan
. .\venv\Scripts\Activate.ps1

# 3. 사전 설정 및 하드웨어 진단을 위해 launch.bat을 실행합니다.
Write-Host "하드웨어 진단 및 환경 설정을 위해 launch.bat을 호출합니다..." -ForegroundColor Cyan
cmd.exe /c launch.bat

# 4. 메인 프로그램을 실행합니다.
# (참고: launch.bat 내부에서 이미 app_launcher.py가 호출 및 종료된 후 제어권이 넘어옵니다)
Write-Host "AMEVA Benchmark Suite를 실행합니다..." -ForegroundColor Cyan
python src/app_launcher.py
