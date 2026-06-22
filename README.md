# Gmail Chat Mirror

Gmail 메일 스레드를 Slack 앱 DM의 Slack 쓰레드로 미러링하는 self-hosted v1 도구입니다.

각 사용자는 자기 Mac, Windows PC, 개인 서버, 미니 PC, NAS 등에서 직접 실행합니다. 메일 본문과 Gmail 토큰은 각자 실행 환경에 저장되고, Slack에는 회사 Slack 앱 봇이 메시지를 보냅니다.

---

## 제일 쉬운 설치 순서

아래 순서대로 하면 됩니다. 중간에 나오는 질문에는 값을 복사해서 붙여넣고 Enter를 누르면 됩니다.

설치 전에 준비할 것:

1. Gmail OAuth JSON 파일
2. Slack Bot Token
3. 내 Slack User ID

각 값을 어디서 가져오는지는 아래 상세 설명에 있습니다.

### macOS

터미널을 열고 프로젝트 폴더로 이동한 뒤 아래만 복붙합니다.

```bash
chmod +x ops/setup-macos.sh
./ops/setup-macos.sh
```

설치가 끝난 뒤 계속 실행:

```bash
source .venv/bin/activate
python -m app.main
```

Mac을 켤 때 자동 실행하려면 아래의 `Mac 자동 실행 설정` 섹션을 봅니다. 자동 실행 파일에는 설치 경로가 들어가므로, 내 폴더 위치에 맞는지 한 번 확인해야 합니다.

### Windows

PowerShell을 열고 프로젝트 폴더로 이동한 뒤 아래만 복붙합니다.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\ops\setup-windows.ps1
```

설치가 끝난 뒤 계속 실행:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.main
```

Windows 로그인 시 자동 실행하려면:

```powershell
.\ops\install-windows-task.ps1
Start-ScheduledTask -TaskName GmailChatMirror
```

---

## 동작 방식

```text
Gmail thread
  ├ 메일 1
  ├ 메일 2
  └ 새 답장

Slack 앱 DM
  └ 부모 메시지: 제목 + 첫 발신자 + 첫 메일 수신일
      ├ 메일 1
      ├ 메일 2
      └ 새 답장
```

기본 운영 정책:

- 전체 과거 메일함을 한 번에 Slack에 올리지 않습니다.
- 처음 실행 시 최근 메일은 “이미 본 것”으로만 기록합니다.
- 이후 새 메일/답장이 생기면 Slack에 미러링합니다.
- 새 답장이 달린 Gmail thread가 Slack에 아직 없으면, 그 thread 하나만 과거 메일까지 가져와 Slack thread로 만듭니다.
- Gmail thread가 이미 Slack에 있으면 새 답장만 기존 Slack thread에 추가합니다.

예시:

```text
기존 Gmail thread A에 메일 13개 있음
이후 14번째 답장이 새로 옴

결과:
Slack 부모글 A
  ├ 1번째 메일
  ├ 2번째 메일
  ├ ...
  ├ 13번째 메일
  └ 14번째 새 답장
```

---

## 준비물

사용자별로 필요한 것:

- 회사 Gmail 계정
- 회사 Slack 계정
- macOS 또는 Windows
- 항상 켜둘 컴퓨터 또는 서버

공통으로 필요한 것:

- 회사 Slack 앱의 Bot Token
- Gmail OAuth Client JSON 파일

---

## 1. 설치: macOS

프로젝트 폴더에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

선택 사항: 인용문 제거 품질을 더 높이고 싶을 때만 설치합니다.

```bash
python -m pip install -r requirements-optional.txt
```

Python 3.13에서는 optional 의존성 설치가 실패할 수 있습니다. 실패해도 기본 동작에는 문제가 없습니다.

---

## 1-1. 설치: Windows

PowerShell을 열고 실행합니다.

권장 설치 위치:

```powershell
C:\gmail-chat
```

프로젝트를 `C:\gmail-chat`에 둔 뒤 실행합니다.

```powershell
cd C:\gmail-chat
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

PowerShell에서 스크립트 실행이 막히면 현재 사용자 범위에서만 허용합니다.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

선택 사항:

```powershell
python -m pip install -r requirements-optional.txt
```

optional 의존성 설치가 실패해도 기본 동작에는 문제가 없습니다.

---

## 2. Gmail OAuth 파일 넣기

Gmail을 읽으려면 Google OAuth Client JSON 파일이 필요합니다.

이 파일은 “이 프로그램이 Gmail 읽기 권한을 요청해도 되는 앱인지” Google에 알려주는 설정 파일입니다.

보통은 둘 중 하나입니다.

```text
A. 담당자에게 파일을 받는다
B. 내가 Google Cloud에서 직접 만든다
```

비개발자라면 먼저 담당자에게 아래처럼 요청하세요.

```text
Gmail Chat Mirror 설정에 필요한 Google OAuth Client JSON 파일을 전달해 주세요.
Application type은 Desktop app이어야 합니다.
```

파일을 받았다면 아래 위치에 저장합니다.

```text
credentials/google-oauth-client.json
```

폴더가 없으면 직접 만듭니다.

macOS:

```bash
mkdir -p credentials
```

Windows:

```powershell
New-Item -ItemType Directory -Force credentials
```

파일명은 반드시 아래처럼 맞추는 것이 가장 쉽습니다.

```text
google-oauth-client.json
```

결과적으로 이런 구조가 되어야 합니다.

```text
gmail-chat/
  credentials/
    google-oauth-client.json
```

파일명이 다르면 `.env`에서 `GOOGLE_CLIENT_SECRET_FILE` 값을 실제 파일명으로 바꿉니다.

```env
GOOGLE_CLIENT_SECRET_FILE=credentials/google-oauth-client.json
```

### Gmail OAuth 파일을 직접 만드는 경우

담당자에게 받을 수 없다면 Google Cloud에서 직접 만듭니다.

아래 사이트를 사용합니다.

```text
Google Cloud Console:
https://console.cloud.google.com/

Google Cloud APIs & Services:
https://console.cloud.google.com/apis/dashboard

Google OAuth Clients:
https://console.cloud.google.com/apis/credentials
```

만드는 순서:

1. Google Cloud Console 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. `APIs & Services`로 이동
4. `Enable APIs and Services` 클릭
5. `Gmail API` 검색
6. `Gmail API` 활성화
7. `OAuth consent screen` 설정
   - 회사 Google Workspace 내부용이면 `Internal` 선택
   - 개인 계정/외부 테스트면 `External` 선택 후 테스트 사용자에 내 Gmail 추가
8. `Credentials`로 이동
9. `Create Credentials` 클릭
10. `OAuth client ID` 선택
11. Application type을 `Desktop app`으로 선택
12. 이름 입력
    - 예: `gmail-chat`
13. 생성 후 JSON 다운로드
14. 다운로드한 JSON 파일을 아래 위치에 저장

```text
credentials/google-oauth-client.json
```

주의:

- Application type은 반드시 `Desktop app`으로 만듭니다.
- Gmail API가 활성화되어 있어야 합니다.
- 회사 Workspace 정책에 따라 관리자의 승인이 필요할 수 있습니다.
- 이 파일은 GitHub에 올리지 않습니다.

---

## 3. Slack 앱 준비하기

Slack은 워크스페이스마다 앱 설치가 필요합니다.

이미 사용할 Slack 앱이 설치되어 있고 Bot Token을 받을 수 있다면 `3-1`만 보면 됩니다.

다른 워크스페이스에서 쓰거나, 내가 만든 Slack 앱을 다른 사람이 사용할 수 없다면 `3-2`에 따라 각자 Slack 앱을 새로 만들어야 합니다.

---

## 3-1. 기존 Slack 앱의 Bot Token 받기

이미 회사 Slack 앱이 설치되어 있다면 새 앱을 만들 필요는 없습니다.

이 경우 사용자는 Slack Bot Token을 직접 만들지 않고, 담당자에게 받아서 `.env`에 넣으면 됩니다.

담당자에게 이렇게 요청하세요.

```text
Gmail Chat Mirror 설정에 필요한 Slack Bot Token을 전달해 주세요.
xoxb- 로 시작하는 Bot User OAuth Token 값이 필요합니다.
필요 권한은 chat:write, im:write 입니다.
```

토큰은 비밀번호와 같으므로 가능하면 아래 방식으로 전달받으세요.

```text
권장:
- 1Password
- Bitwarden
- 회사 비밀번호 관리 도구
- 1회성 secret 공유 링크

비추천:
- Slack 채널에 그대로 붙여넣기
- Google Docs/Notion에 적어두기
- GitHub에 올리기
```

토큰을 받으면 `.env`에 넣습니다.

```env
SLACK_BOT_TOKEN=xoxb-...
```

### 담당자가 Slack Bot Token을 복사하는 위치

Slack Bot Token 복사 위치:

1. 아래 사이트 접속

```text
Slack Apps:
https://api.slack.com/apps
```

2. 회사 Slack 앱 선택
3. 왼쪽 메뉴에서 `OAuth & Permissions` 클릭
4. `OAuth Tokens for Your Workspace` 섹션 찾기
5. `Bot User OAuth Token` 복사
6. `xoxb-...` 형태의 값인지 확인

직접 주소:

```text
Slack App 관리:
https://api.slack.com/apps

Slack OAuth 문서:
https://docs.slack.dev/authentication/installing-with-oauth/
```

필요한 Bot Token Scopes:

```text
chat:write
im:write
```

권한을 새로 추가했다면 `OAuth & Permissions` 화면에서 `Reinstall to Workspace`를 한 번 해야 합니다.

주의: `SLACK_BOT_TOKEN`은 비밀번호처럼 취급합니다. Git에 올리지 말고, 채팅에도 붙여넣지 않는 것이 좋습니다.

---

## 3-2. Slack 앱 새로 만들기

내가 만든 Slack 앱을 다른 사람이 사용할 수 없거나, 다른 워크스페이스에서 쓰려면 각자 Slack 앱을 만들어서 설치해야 합니다.

Slack 앱 생성 사이트:

```text
https://api.slack.com/apps
```

생성 순서:

1. `Create New App` 클릭
2. `From scratch` 선택
3. App Name 입력
   - 예: `gmail-chat`
4. 설치할 Slack Workspace 선택
5. `Create App` 클릭

권한 추가:

1. 왼쪽 메뉴에서 `OAuth & Permissions` 클릭
2. `Scopes` 섹션으로 이동
3. `Bot Token Scopes`에서 `Add an OAuth Scope` 클릭
4. 아래 권한 2개 추가

```text
chat:write
im:write
```

권한 의미:

- `chat:write`: Slack에 메시지를 보냅니다.
- `im:write`: 사용자와 봇 사이의 DM을 엽니다.

워크스페이스 설치:

1. `OAuth & Permissions` 화면 상단으로 이동
2. `Install to Workspace` 클릭
3. 권한 허용
4. 설치가 끝나면 `Bot User OAuth Token`이 생성됩니다.
5. `xoxb-...` 형태의 토큰을 복사합니다.

`.env`에 넣습니다.

```env
SLACK_BOT_TOKEN=xoxb-...
```

권한을 나중에 추가하거나 변경했다면 반드시 다시 설치해야 합니다.

```text
OAuth & Permissions
→ Reinstall to Workspace
```

참고 문서:

```text
Slack 앱 생성:
https://api.slack.com/apps

Slack OAuth 설치:
https://docs.slack.dev/authentication/installing-with-oauth/

Slack 권한 scopes:
https://docs.slack.dev/reference/scopes/
```

---

## 4. 내 Slack User ID 복사하기

이 도구는 Slack 채널이 아니라 앱 DM으로 메일을 보냅니다. 그래서 각 사용자의 Slack User ID가 필요합니다.

Slack User ID 찾는 법:

1. Slack 웹 또는 앱 열기

```text
Slack Web:
https://app.slack.com/
```

2. 내 프로필 열기
3. 더보기 메뉴 `...` 클릭
4. `멤버 ID 복사` 또는 `Copy member ID` 클릭
5. `U...` 형태의 값을 복사

`.env`에 넣습니다.

```env
SLACK_CHANNEL_ID=
SLACK_USER_ID=U...
```

---

## 5. `.env` 설정 예시

최소 설정은 아래와 같습니다.

```env
GMAIL_AUTH_MODE=oauth
GOOGLE_CLIENT_SECRET_FILE=credentials/google-oauth-client.json
GOOGLE_TOKEN_FILE=data/google-token.json
GMAIL_QUERY=

SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=
SLACK_USER_ID=U...

GMAIL_BACKFILL_THREADS=false
GMAIL_BACKFILL_ON_FIRST_SEEN_THREAD=true
GMAIL_MAX_THREAD_MESSAGES=30
BOOTSTRAP_EXISTING_MESSAGES=true

POLL_INTERVAL_SECONDS=60
FETCH_LIMIT=50
DATABASE_PATH=data/mirror.sqlite3
LOG_FILE=logs/gmail-chat.log
LOG_LEVEL=INFO
```

설정 의미:

- `GMAIL_BACKFILL_THREADS=false`: 전체 과거 메일함을 소급하지 않음
- `GMAIL_BACKFILL_ON_FIRST_SEEN_THREAD=true`: 새 답장이 생긴 thread 하나만 과거 포함해서 Slack thread 생성
- `GMAIL_MAX_THREAD_MESSAGES=30`: 한 Gmail thread에서 최대 30개 메일까지만 가져옴
- `FETCH_LIMIT=50`: 최초 bootstrap 또는 Gmail history 기준점이 없을 때 최근 50개를 기준으로 확인
- `POLL_INTERVAL_SECONDS=60`: 60초마다 확인

Polling 누락 방지:

- Gmail OAuth 모드에서는 `historyId`를 로컬 DB에 저장합니다.
- 첫 기준점 이후에는 `FETCH_LIMIT`만 보는 게 아니라 Gmail history API로 “지난 실행 이후 추가된 메시지”를 가져옵니다.
- 그래서 1분 사이에 메일이 10개 이상 와도 Gmail history에 남아 있으면 놓치지 않습니다.
- `FETCH_LIMIT`는 최초 bootstrap, 초기 기준점 생성, history 기준점이 없는 예외 상황에서만 중요합니다.

---

## 6. Gmail 연결

브라우저가 열리면 회사 Gmail 계정으로 로그인하고 권한을 허용합니다.

macOS:

```bash
source .venv/bin/activate
python scripts/gmail_oauth_probe.py --authorize-only
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\gmail_oauth_probe.py --authorize-only
```

성공하면 아래 파일이 생깁니다.

```text
data/google-token.json
```

연결 확인:

macOS:

```bash
python scripts/gmail_oauth_probe.py --limit 5
```

Windows:

```powershell
python scripts\gmail_oauth_probe.py --limit 5
```

최근 메일 정보가 JSON으로 나오면 Gmail 연결은 성공입니다.

---

## 7. Slack 연결 확인

Slack 앱 DM으로 테스트 메시지를 보냅니다.

macOS:

```bash
source .venv/bin/activate
python scripts/slack_probe.py
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\slack_probe.py
```

성공하면 Slack 앱 DM에 테스트 부모 메시지와 reply가 하나씩 보입니다.

---

## 8. 기존 메일 Bootstrap

처음 실행 전에 현재 최근 메일을 “이미 본 것”으로 기록합니다. 이 단계에서는 Slack에 메시지를 보내지 않습니다.

macOS:

```bash
source .venv/bin/activate
python -m app.main --bootstrap-existing --limit 20
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.main --bootstrap-existing --limit 20
```

이후부터 새로 들어오거나 내가 보낸 Gmail 답장만 Slack에 미러링됩니다.

---

## 9. 한 번 실행해보기

macOS:

```bash
source .venv/bin/activate
python -m app.main --once
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.main --once
```

새 메일이 없으면:

```text
Posted 0 new Slack message(s).
```

새 메일이 있으면 Slack 앱 DM에 부모 메시지와 thread replies가 생성됩니다.

---

## 10. 계속 실행하기

터미널에서 계속 켜둘 때:

macOS:

```bash
source .venv/bin/activate
python -m app.main
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.main
```

중단하려면 `Ctrl+C`를 누릅니다.

---

## 11. Mac 자동 실행 설정

Mac을 켤 때 자동으로 실행하려면 `launchd`를 사용합니다.

먼저 `ops/run-gmail-chat.sh`와 `ops/com.andan.gmail-chat.plist` 안의 경로가 내 프로젝트 위치와 맞는지 확인합니다. 현재 예시는 아래 경로를 기준으로 되어 있습니다.

```text
/Users/andan/googlechat
```

다른 위치에 설치했다면 두 파일의 경로를 먼저 수정합니다.

```bash
chmod +x ops/run-gmail-chat.sh
cp ops/com.andan.gmail-chat.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.andan.gmail-chat.plist
```

실행 중지:

```bash
launchctl unload ~/Library/LaunchAgents/com.andan.gmail-chat.plist
```

실행 여부 확인:

```bash
launchctl list | grep com.andan.gmail-chat
```

로그 확인:

```bash
tail -f logs/gmail-chat.log
```

---

## 11-1. Windows 자동 실행 설정

Windows 로그인 시 자동 실행하려면 작업 스케줄러를 사용합니다.

전제:

- 프로젝트 위치가 `C:\gmail-chat`
- `.env` 설정 완료
- Gmail 연결 완료
- Slack 연결 확인 완료

PowerShell을 관리자 권한이 아닌 일반 사용자로 열고 실행합니다.

```powershell
cd C:\gmail-chat
.\ops\install-windows-task.ps1
```

바로 시작:

```powershell
Start-ScheduledTask -TaskName GmailChatMirror
```

중지:

```powershell
Stop-ScheduledTask -TaskName GmailChatMirror
```

삭제:

```powershell
cd C:\gmail-chat
.\ops\uninstall-windows-task.ps1
```

로그 확인:

```powershell
Get-Content logs\gmail-chat.log -Wait
```

프로젝트를 `C:\gmail-chat`이 아닌 다른 위치에 둘 경우 아래 파일의 경로를 수정해야 합니다.

```text
ops/run-gmail-chat.ps1
ops/install-windows-task.ps1
```

---

## 11-2. 개인 서버에서 계속 실행하기

개인 서버, 미니 PC, NAS, 사무실 상시 PC에서 실행해도 됩니다.

핵심 조건:

- 전원이 계속 켜져 있어야 함
- 인터넷 연결이 유지되어야 함
- Gmail OAuth 인증을 최초 1회 완료해야 함
- `python -m app.main` 프로세스가 계속 실행되어야 함

Linux 서버에서는 아직 systemd 파일을 제공하지 않습니다. 임시로는 `tmux`, `screen`, `nohup` 중 하나로 실행할 수 있습니다.

```bash
source .venv/bin/activate
python -m app.main
```

---

## 12. 자주 생기는 문제

### Slack에 메시지가 안 옵니다

확인할 것:

- `.env`의 `SLACK_BOT_TOKEN`이 `xoxb-...` 형태인지
- `.env`의 `SLACK_USER_ID`가 `U...` 형태인지
- Slack 앱에 `chat:write`, `im:write` 권한이 있는지
- 권한 추가 후 `Reinstall to Workspace`를 했는지

테스트:

```bash
python scripts/slack_probe.py
```

### Gmail 연결에서 차단됩니다

회사 Google Workspace 정책에 따라 OAuth 앱 승인이 필요할 수 있습니다.

확인할 것:

- Gmail API가 활성화된 OAuth Client JSON인지
- OAuth consent screen이 회사 내부 사용자에게 허용되어 있는지
- 브라우저 로그인 계정이 회사 Gmail 계정인지

테스트:

```bash
python scripts/gmail_oauth_probe.py --authorize-only
```

### 과거 메일이 너무 많이 올라옵니다

아래 설정을 확인합니다.

```env
GMAIL_BACKFILL_THREADS=false
GMAIL_BACKFILL_ON_FIRST_SEEN_THREAD=true
GMAIL_MAX_THREAD_MESSAGES=30
FETCH_LIMIT=5
```

전체 소급을 막으려면 `GMAIL_BACKFILL_THREADS=false`를 유지합니다.

### 같은 메일이 중복으로 올라옵니다

상태 DB는 아래 파일입니다.

```text
data/mirror.sqlite3
```

이 파일을 삭제하거나 새 DB를 쓰면 기존 처리 기록이 사라져 중복 게시될 수 있습니다.

---

## 13. 개발자용 명령

테스트:

```bash
python -m unittest discover -s tests
```

문법 검사:

```bash
python -m compileall app scripts tests
```

DB만 초기화:

```bash
python -m app.main --init-db
```

---

## 보안 주의

Git에 올리면 안 되는 파일:

```text
.env
data/google-token.json
credentials/*.json
data/*.sqlite3
```

이 파일들은 `.gitignore`에 포함되어 있습니다.

노출되면 재발급해야 하는 값:

- `SLACK_BOT_TOKEN`
- `data/google-token.json`
- Gmail OAuth Client JSON
