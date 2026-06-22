# Gmail → Slack 미러링 (가칭) — MVP 기획문서

> Gmail 스레드를 Slack 채널에 쓰레드 형태로 그대로 미러링해서, **보기 편하게** 만드는 개인용 도구
> 작성일: 2026-06-18 · 상태: MVP 기획 (v0, 읽기 전용) · 갱신: 아키텍처를 웹앱 → Slack 미러링으로 전환

---

## 1. 배경 / 문제정의

업무 메일은 한 메일에 답장이 쌓이면 스레드가 길어지고, 길어질수록 흐름 파악·관리가 어렵다. Slack 스레드처럼 메시지가 시간순으로 쭉 쌓이면 보기 편하다.

→ **별도 UI를 만들지 말고, Gmail 스레드를 Slack 채널에 미러링**한다. Slack이 곧 뷰어.

## 2. 목표 / 비목표

**목표 (v0)**
- 새 메일이 오면 Slack 채널에 메시지로 게시
- 같은 이메일 스레드의 후속 메일은 **같은 Slack 쓰레드에 답글로 쌓임**
  - ① 받은 답장 (inbound) → 쓰레드에 쌓임
  - ② 내가 Gmail에서 보낸 답장 → 같은 쓰레드에 "내 메시지"로 쌓임
- 인용문/서명 제거 → 각 메시지의 "새로 쓴 내용"만 표시
- 혼자, 로컬(Mac Studio)에서 실행

**비목표 (안 한다)**
- ③ Slack에서 답장 작성 → 이메일 발송 (양방향) — **목적이 "보기"라 제외**
- 웹 UI (Slack이 UI)
- 멀티 계정, 실시간 푸시, 검색/라벨 UI, 첨부 다운로드(표시만)

> ③을 빼면서 Socket Mode·SMTP 발송·에코 루프 문제가 전부 제거됨 → 순수 단방향 미러로 단순화.

## 3. 핵심 가설 & 검증 포인트 ⭐

> **"Gmail 스레드를 Slack 쓰레드로 미러링하면, 긴 메일 관리가 실제로 편해진다."**

- 실험 환경이 진짜 Slack이라, 채팅뷰 가설을 가장 깨끗하게 검증할 수 있음
- yes → 동기화 안정화·편의기능 / no → 방향 재검토

## 4. 아키텍처

```
Gmail (IMAP, All Mail)
   │  poll (N초)
   ▼
로컬 봇 (Python, Mac Studio)
   ├─ X-GM-THRID로 스레드 식별
   ├─ talon으로 인용문/서명 제거
   ├─ SQLite: 스레드 매핑 + 처리한 메시지 기록
   ▼
Slack Web API  chat.postMessage(thread_ts)
   ▼
Slack 채널 (= 뷰어)
```

- 봇은 **로컬에서만 실행** → 메일 본문·자격증명이 기기 밖으로 안 나감
- 이벤트 수신 없음(읽기 전용) → Socket Mode 불필요, 공개 서버·호스팅 불필요

## 5. 인증 방식

| 대상 | 방식 | 비고 |
|------|------|------|
| Gmail | **Gmail API OAuth** | Workspace에서 App Password가 막힌 경우의 기본 경로. Google Cloud OAuth Client ID 필요 |
| Gmail 대체 | App Password + IMAP | App Password가 허용되는 계정에서만 사용. Cloud Console 불필요 |
| Slack | **Bot Token** (`xoxb-`) | `api.slack.com/apps`에서 앱 생성 → `chat:write` 스코프 → 워크스페이스 설치. Socket Mode/이벤트 구독 불필요 |

- Slack 봇이 게시할 채널에 **봇을 초대**해둬야 함
- ⚠️ 회사 계정(sellmate.co.kr, Workspace)은 관리자가 앱 비밀번호를 막아뒀을 수 있음 → 막히면 Gmail API OAuth 경로 사용. OAuth 앱도 막혀 있으면 Workspace 관리자 승인이 필요.

## 6. 기술 스택

| 영역 | 선택 | 비고 |
|------|------|------|
| 언어 | Python (단일) | Gmail·talon·Slack 한 언어로 |
| Gmail 접속/파싱 | Gmail API OAuth, `email` | Workspace App Password 차단에 대응 |
| Gmail 대체 접속 | `imaplib` | App Password 허용 계정에서만 사용 |
| 인용문/서명 제거 | `talon` (Mailgun) | **핵심 의존성** |
| Slack 게시 | `slack_sdk` (WebClient) | `chat.postMessage` (이벤트 없으니 Bolt 불필요) |
| 매핑/상태 | SQLite | thread 매핑 + 처리 기록 |
| 실행 | 로컬 루프 / launchd / cron | |

IMAP: `imap.gmail.com:993` (SSL) · 폴링 대상: `[Gmail]/All Mail` (받은+보낸 메일 다 포함 → ② 충족)

## 7. 핵심 처리 로직

**(1) 스레드 식별** — IMAP FETCH로 `X-GM-THRID` 획득. 받은/보낸 메일을 같은 스레드로 묶어줌.

**(2) 인용문 제거** ⭐ — `talon.quotations.extract_from()`로 "새로 쓴 본문"만 추출. 안 떼면 말풍선마다 전체 히스토리가 들어가 미러링 의미 없음.

**(3) 발신자 구분** — `From`이 내 주소면 "나"로 표시(②), 아니면 상대.

**(4) 게시** — 스레드 매핑 조회:
- 매핑 있음 → `chat.postMessage(channel, text, thread_ts=매핑값)` (같은 쓰레드에 답글)
- 매핑 없음 → 새 부모 메시지 게시 → 반환된 `ts`를 매핑에 저장

**의사코드**
```
every N seconds:
    msgs = fetch_new_from_all_mail()   # 처리 안 한 UID만
    for m in msgs:
        thrid = m["X-GM-THRID"]
        body  = talon.extract_from(m.text)
        label = "나" if from_me(m) else m.sender
        if thrid in mapping:
            post(channel, body, thread_ts=mapping[thrid], who=label)
        else:
            ts = post(channel, f"{m.subject}\n{body}", who=label)
            mapping[thrid] = ts
        mark_processed(m.uid)
```

## 8. 리스크 / 함정

| 리스크 | 대응 |
|--------|------|
| 재폴링 시 같은 메일 중복 게시 | 처리한 메시지 UID/Message-ID를 SQLite에 기록 → 스킵 |
| 폴링 지연(즉시 아님) | N=30~60초. 거의 실시간 원하면 IMAP IDLE (선택, 까다로움) |
| 봇 가동 전 과거 스레드 | 봇이 처음 본 메일부터 부모 생성. 과거 소급은 별도 작업 |
| 앱 비밀번호 노출 | env var로 분리, 폐기·재발급 가능 |
| 회사(Workspace) 앱 비밀번호 차단 | 착수 시 우선 테스트 |
| 무료 Slack 90일 히스토리 | 원본은 Gmail에 있으니 영향 작음 |

## 9. 진행 순서

1. **(검증)** 회사 계정 App Password IMAP 접속 가능 여부 테스트
2. Slack 앱 생성 → `chat:write` 봇 토큰 발급 → 테스트 채널에 봇 초대
3. Gmail IMAP 접속 → `[Gmail]/All Mail`에서 스레드 1개 가져와 `X-GM-THRID`로 묶기
4. `talon` 파이프라인 → 본문만 깔끔히 추출 확인
5. `chat.postMessage`로 스레드 1개를 Slack 쓰레드로 미러링 (PoC)
6. SQLite 매핑 + 중복 방지 + 폴링 루프
7. **(핵심 가설 검증)** 실제 긴 스레드로 "보기 편해지나?" 판단
8. yes → 동기화 안정화·편의기능 / no → 방향 재검토
