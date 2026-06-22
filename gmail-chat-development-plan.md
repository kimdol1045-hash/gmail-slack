# Gmail → Slack 미러링 MVP 개발계획

> 기준 문서: `gmail-chat-mvp-plan.md`  
> 목표: Gmail 스레드를 Slack 쓰레드로 단방향 미러링하는 로컬 MVP 구현  
> 작성일: 2026-06-19

---

## 1. 개발 목표

Gmail의 긴 이메일 스레드를 Slack 쓰레드 형태로 미러링해서, 별도 웹 UI 없이 Slack에서 메일 흐름을 보기 쉽게 만든다.

MVP의 핵심 범위는 다음과 같다.

- 새 Gmail 메일을 Slack 채널에 게시
- 같은 Gmail 스레드의 후속 메일은 같은 Slack 쓰레드에 답글로 게시
- 받은 메일과 내가 Gmail에서 보낸 답장을 모두 미러링
- 인용문과 서명을 제거해 각 메일에서 새로 작성된 본문만 표시
- 로컬 Mac Studio에서 실행
- Slack에서 이메일 답장을 보내는 양방향 기능은 제외

---

## 2. 전체 개발 단계

1. Gmail OAuth 또는 IMAP 접속 가능 여부 검증
2. Slack Bot API 게시 검증
3. 프로젝트 골격 구성
4. Gmail 수집 PoC 구현
5. 메일 본문 정리 파이프라인 구현
6. Slack 쓰레드 미러링 구현
7. SQLite 기반 상태 관리와 중복 방지 구현
8. 폴링 루프 구현
9. 로컬 운영 방식 정리
10. 실제 긴 메일 스레드로 사용성 검증

---

## 3. Phase 0: 착수 전 기술 검증

### 목표

앱 개발 전에 막힐 수 있는 인증과 API 접근 가능 여부를 먼저 확인한다.

### 작업

- Gmail 계정에서 App Password 발급 가능 여부 확인
- App Password가 막힌 경우 Gmail API OAuth 경로로 전환
- OAuth Client ID 생성 가능 여부 확인
- OAuth 경로에서 Gmail API `threadId` 수신 여부 확인
- IMAP 경로를 쓸 경우 IMAP 로그인 가능 여부 확인
- IMAP 경로를 쓸 경우 `[Gmail]/All Mail` mailbox 접근 가능 여부 확인
- IMAP 경로를 쓸 경우 IMAP FETCH 결과에서 `X-GM-THRID` 수신 여부 확인
- Slack 앱 생성
- Slack Bot Token 발급
- `chat:write` 권한 설정
- 테스트 채널에 봇 초대
- Slack `chat.postMessage` 호출 가능 여부 확인

### 완료 기준

- Gmail 메일 1개를 로컬에서 읽을 수 있다.
- OAuth 경로에서는 Gmail API `threadId`, `Message-ID`, `From`, `Subject`, `Date`를 추출할 수 있다.
- IMAP 경로에서는 `X-GM-THRID`, `Message-ID`, `From`, `Subject`, `Date`를 추출할 수 있다.
- Slack 테스트 채널에 봇 메시지 1개를 게시할 수 있다.

### 산출물

- `scripts/gmail_oauth_probe.py`
- `scripts/imap_probe.py`
- `scripts/slack_probe.py`

---

## 4. Phase 1: 프로젝트 골격 구성

### 목표

이후 기능을 붙이기 쉬운 최소 구조를 만든다.

### 권장 디렉터리 구조

```text
gmail-chat/
  app/
    __init__.py
    config.py
    db.py
    gmail_api_client.py
    gmail_client.py
    mail_parser.py
    slack_client.py
    mirror.py
    main.py
  scripts/
    gmail_oauth_probe.py
    imap_probe.py
    slack_probe.py
  data/
    .gitkeep
  credentials/
    .gitkeep
  .env.example
  requirements.txt
  README.md
```

### 주요 설정값

```env
GMAIL_EMAIL=
GMAIL_AUTH_MODE=oauth
GMAIL_APP_PASSWORD=
GMAIL_MAILBOX=[Gmail]/All Mail
GOOGLE_CLIENT_SECRET_FILE=credentials/google-oauth-client.json
GOOGLE_TOKEN_FILE=data/google-token.json
GMAIL_QUERY=
SLACK_BOT_TOKEN=
SLACK_CHANNEL_ID=
POLL_INTERVAL_SECONDS=60
DATABASE_PATH=data/mirror.sqlite3
```

### 완료 기준

- `.env` 기반 설정을 로딩할 수 있다.
- SQLite 데이터베이스를 초기화할 수 있다.
- `python -m app.main` 형태로 앱을 실행할 수 있다.

---

## 5. Phase 2: Gmail 수집 PoC

### 목표

Gmail에서 최근 메일을 가져오고, 스레드 식별에 필요한 메타데이터를 안정적으로 추출한다.

### 작업

- IMAP SSL 연결
- Gmail App Password 로그인
- `[Gmail]/All Mail` 선택
- 최근 N개 메일 검색
- UID, `Message-ID`, `X-GM-THRID`, `Subject`, `From`, `To`, `Date` 추출
- plain text 본문 추출
- plain text가 없을 경우 HTML 본문을 text로 변환
- `From` 주소 기준으로 내가 보낸 메일인지 판별

### 주의사항

- Gmail IMAP UID는 mailbox 기준이므로 `Message-ID`도 함께 저장한다.
- `[Gmail]/All Mail`을 사용해야 받은 메일과 보낸 메일을 같은 흐름에서 볼 수 있다.
- 같은 이메일 스레드의 받은 메일과 보낸 메일이 같은 `X-GM-THRID`로 묶이는지 반드시 확인한다.

### 완료 기준

- 최근 메일 목록을 로그나 JSON으로 출력할 수 있다.
- 같은 Gmail 스레드의 메일들이 같은 `X-GM-THRID`로 묶인다.
- 내가 보낸 메일과 상대가 보낸 메일을 구분할 수 있다.

---

## 6. Phase 3: 본문 정리 파이프라인

### 목표

Slack에 게시되는 메시지가 중복 인용문 없이 읽을 만한 형태가 되도록 만든다.

### 작업

- `talon.quotations.extract_from()` 적용
- 가능한 경우 서명 제거 적용
- HTML 메일 fallback 처리
- 빈 본문 또는 정리 실패 케이스 처리
- Slack 메시지 포맷 결정
- 너무 긴 본문에 대한 제한 정책 결정

### Slack 표시 포맷 초안

부모 메시지:

```text
*메일 스레드 시작*
*Subject:* Re: 계약서 검토 요청
*From:* 홍길동

본문 내용...
```

후속 답글:

```text
*홍길동* · 2026-06-19 14:31
본문 내용...
```

내가 보낸 답글:

```text
*나* · 2026-06-19 14:42
본문 내용...
```

### 완료 기준

- 긴 Gmail 답장 스레드에서 이전 인용문이 반복 게시되지 않는다.
- Slack에서 각 메시지가 새로 작성된 본문 중심으로 보인다.
- 한글/영문 혼합 메일이 깨지지 않는다.

---

## 7. Phase 4: Slack 미러링 구현

### 목표

Gmail 스레드 하나가 Slack 쓰레드 하나로 매핑되도록 만든다.

### 작업

- Slack WebClient 래퍼 구현
- 새 Gmail 스레드면 Slack 부모 메시지 생성
- 기존 Gmail 스레드면 `thread_ts`로 답글 생성
- Slack API 응답의 `ts` 저장
- Slack API 실패 시 처리 상태를 저장하지 않고 다음 폴링에서 재시도

### 매핑 로직

```text
Gmail X-GM-THRID 없음
  → 처리 불가 또는 fallback 정책 적용

Gmail X-GM-THRID가 SQLite에 없음
  → Slack 부모 메시지 게시
  → 반환된 ts를 thread mapping으로 저장

Gmail X-GM-THRID가 SQLite에 있음
  → 저장된 slack_thread_ts로 Slack 답글 게시
```

### 완료 기준

- Gmail 스레드 1개가 Slack 스레드 1개로 재현된다.
- 후속 메일이 같은 Slack thread에 쌓인다.
- Slack API 실패 시 중복 처리나 유실 없이 재시도할 수 있다.

---

## 8. Phase 5: SQLite 상태 관리와 중복 방지

### 목표

앱을 재실행하거나 재폴링해도 같은 메일이 중복 게시되지 않도록 한다.

### 테이블 초안

```sql
create table if not exists threads (
  gmail_thread_id text primary key,
  slack_channel_id text not null,
  slack_thread_ts text not null,
  subject text,
  created_at text not null
);

create table if not exists messages (
  message_id text primary key,
  gmail_uid text,
  gmail_thread_id text not null,
  slack_channel_id text not null,
  slack_ts text,
  direction text not null,
  subject text,
  processed_at text not null
);
```

### 작업

- DB 초기화 함수 구현
- 처리 완료된 `Message-ID` 저장
- 이미 처리한 `Message-ID`는 스킵
- `gmail_thread_id` 기준 Slack thread mapping 조회
- Slack 게시 성공 후에만 `messages`에 처리 완료 기록

### 완료 기준

- 앱 재실행 후에도 기존 메일이 다시 게시되지 않는다.
- 같은 Gmail 스레드의 새 메일은 기존 Slack thread에 이어진다.
- SQLite 파일만 보존하면 상태가 유지된다.

---

## 9. Phase 6: 폴링 루프 구현

### 목표

로컬에서 계속 켜둘 수 있는 MVP 실행 루프를 만든다.

### 작업

- `POLL_INTERVAL_SECONDS`마다 Gmail 확인
- 새 메일만 필터링
- 처리 중 예외 발생 시 앱 전체가 죽지 않도록 처리
- Gmail/Slack 오류 로깅
- 종료 신호 처리

### 기본 정책

- 초기 폴링 간격은 60초
- 거의 실시간성이 필요하면 추후 IMAP IDLE 검토
- MVP에서는 IMAP IDLE을 제외하고 단순 폴링으로 시작

### 완료 기준

- 앱을 1시간 이상 켜둬도 중복 없이 동작한다.
- 새로 받은 메일이 Slack에 반영된다.
- 내가 Gmail에서 보낸 답장이 Slack에 반영된다.

---

## 10. Phase 7: 로컬 운영 정리

### 목표

Mac Studio에서 수동 실행 또는 자동 실행할 수 있게 정리한다.

### 작업

- `.env.example` 작성
- `README.md` 작성
- 설치 명령 정리
- 수동 실행 명령 정리
- 로그 위치 정리
- `launchd` plist 예시 작성
- Gmail App Password와 Slack Bot Token 폐기 방법 문서화

### 완료 기준

- 새 환경에서 README만 보고 실행할 수 있다.
- 터미널에서 수동 실행할 수 있다.
- 필요하면 `launchd`로 자동 실행할 수 있다.

---

## 11. Phase 8: 실제 사용성 검증

### 목표

기술적으로 동작하는지를 넘어서, Slack 미러링이 실제로 메일 스레드 읽기에 도움이 되는지 판단한다.

### 테스트 케이스

- 짧은 2~3개 답장 스레드
- 긴 10개 이상 답장 스레드
- 내가 중간에 답장한 스레드
- HTML 메일
- 서명이 긴 메일
- 첨부가 있는 메일
- 한글/영문 혼합 메일
- 같은 제목이지만 다른 Gmail thread인 메일

### 판단 기준

- Slack 스레드로 보는 것이 Gmail보다 흐름 파악에 도움이 되는가
- 인용문 제거 품질이 충분한가
- 내가 보낸 메일이 자연스럽게 같은 흐름에 보이는가
- Slack 채널 노이즈가 과하지 않은가
- 계속 켜두고 쓸 만큼 안정적인가

### 완료 기준

- 실제 긴 스레드 3개 이상을 Slack에 미러링해본다.
- 사용성이 충분하면 안정화와 편의 기능으로 넘어간다.
- 사용성이 부족하면 방향을 재검토한다.

---

## 12. 개발 우선순위

### 1순위

- Gmail IMAP 접속 검증
- `X-GM-THRID` 추출 검증
- Slack 메시지 게시 검증
- Gmail thread → Slack thread 매핑
- 중복 게시 방지

### 2순위

- 인용문 제거 품질 개선
- HTML 메일 처리
- 오류 로깅
- 로컬 실행 안정화

### 3순위

- launchd 자동 실행
- 첨부 표시 개선
- 메시지 포맷 개선
- 특정 라벨/발신자 필터링
- IMAP IDLE 검토

---

## 13. 예상 일정

인증 이슈가 없다는 전제에서 MVP 구현 예상 기간은 2~4일이다.

| 일정 | 작업 |
|------|------|
| Day 1 | Gmail IMAP 검증, Slack API 검증, 프로젝트 골격 |
| Day 2 | Gmail 수집, 본문 정리, Slack 미러링 PoC |
| Day 3 | SQLite 상태 관리, 중복 방지, 폴링 루프 |
| Day 4 | 실제 긴 스레드 검증, README, 로컬 운영 정리 |

가장 큰 변수는 회사 Google Workspace에서 App Password, IMAP, 미승인 OAuth 앱을 어디까지 허용하는지다. App Password가 막히면 Gmail API OAuth 경로를 사용하고, OAuth 앱도 막히면 Workspace 관리자 승인이 필요하다.

---

## 14. 첫 구현 순서

가장 먼저 본 앱을 만들지 않고, 아래 순서로 작은 검증 스크립트부터 만든다.

1. `scripts/gmail_oauth_probe.py`
   - Gmail OAuth 로그인
   - 최근 메일 10개 출력
   - Gmail API `threadId` 출력

2. `scripts/imap_probe.py`
   - App Password 사용 가능 시 Gmail IMAP 로그인
   - `[Gmail]/All Mail` 접근
   - 최근 메일 10개 출력
   - `X-GM-THRID` 출력

3. `scripts/slack_probe.py`
   - Slack Bot Token 검증
   - 테스트 채널에 부모 메시지 게시
   - 같은 부모 메시지에 답글 게시

4. `app/mirror.py`
   - Gmail 메일 1개를 Slack에 게시
   - Gmail thread mapping 저장
   - 같은 thread의 후속 메일을 Slack 답글로 게시

5. `app/main.py`
   - 폴링 루프
   - 중복 방지
   - 예외 처리

---

## 15. MVP 완료 정의

MVP는 다음 조건을 만족하면 완료로 본다.

- 로컬에서 앱을 실행할 수 있다.
- Gmail 새 메일이 Slack 채널에 게시된다.
- 같은 Gmail 스레드의 후속 메일이 같은 Slack 쓰레드에 답글로 게시된다.
- 내가 Gmail에서 보낸 답장도 같은 Slack 쓰레드에 표시된다.
- 앱 재실행 후에도 같은 메일이 중복 게시되지 않는다.
- 인용문이 과도하게 반복되지 않는다.
- 실제 긴 메일 스레드 기준으로 Slack에서 흐름을 읽을 수 있다.
