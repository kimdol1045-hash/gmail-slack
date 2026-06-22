#!/bin/zsh
set -eu

cd "$(dirname "$0")/.."

echo "1/5 Python 가상환경을 준비합니다."
python3 -m venv .venv
. .venv/bin/activate

echo "2/5 필요한 패키지를 설치합니다."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "3/5 설정 파일을 만듭니다."
python scripts/setup_env.py

echo "4/5 Gmail을 연결합니다. 브라우저에서 권한을 허용하세요."
python scripts/gmail_oauth_probe.py --authorize-only

echo "5/5 Slack DM 전송을 테스트합니다."
python scripts/slack_probe.py

echo "기존 최근 메일을 Slack에 올리지 않고 기준점으로 기록합니다."
python -m app.main --bootstrap-existing --limit 20

echo ""
echo "설치 완료."
echo "계속 실행하려면:"
echo "source .venv/bin/activate && python -m app.main"

