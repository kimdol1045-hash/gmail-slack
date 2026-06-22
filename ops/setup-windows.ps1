$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "1/5 Python 가상환경을 준비합니다."
py -3 -m venv .venv

Write-Host "2/5 필요한 패키지를 설치합니다."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "3/5 설정 파일을 만듭니다."
& ".\.venv\Scripts\python.exe" scripts\setup_env.py

Write-Host "4/5 Gmail을 연결합니다. 브라우저에서 권한을 허용하세요."
& ".\.venv\Scripts\python.exe" scripts\gmail_oauth_probe.py --authorize-only

Write-Host "5/5 Slack DM 전송을 테스트합니다."
& ".\.venv\Scripts\python.exe" scripts\slack_probe.py

Write-Host "최근 Gmail thread 30개를 Slack에 초기 동기화합니다."
& ".\.venv\Scripts\python.exe" -m app.main --seed-recent-threads --limit 30

Write-Host ""
Write-Host "설치 완료."
Write-Host "계속 실행하려면:"
Write-Host ".\.venv\Scripts\Activate.ps1"
Write-Host "python -m app.main"
