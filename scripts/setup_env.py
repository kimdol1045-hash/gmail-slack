from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DEFAULT_GOOGLE_CLIENT_PATH = ROOT / "credentials" / "google-oauth-client.json"


def main() -> None:
    print("Gmail Chat Mirror 설정 마법사")
    print("=" * 32)
    print("값을 붙여넣고 Enter를 누르면 됩니다.")
    print()

    if ENV_PATH.exists():
        overwrite = _prompt("이미 .env가 있습니다. 다시 만들까요? (y/N)", "n")
        if overwrite.lower() not in {"y", "yes"}:
            print(".env를 변경하지 않았습니다.")
            return

    DEFAULT_GOOGLE_CLIENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)

    oauth_path = _prompt(
        "Google OAuth JSON 파일 경로를 붙여넣으세요. 이미 credentials/google-oauth-client.json에 있으면 Enter",
        str(DEFAULT_GOOGLE_CLIENT_PATH),
    )
    oauth_source = Path(_clean_path(oauth_path)).expanduser()
    if oauth_source != DEFAULT_GOOGLE_CLIENT_PATH:
        if not oauth_source.exists():
            raise SystemExit(f"Google OAuth JSON 파일을 찾을 수 없습니다: {oauth_source}")
        shutil.copyfile(oauth_source, DEFAULT_GOOGLE_CLIENT_PATH)
        print(f"복사 완료: {DEFAULT_GOOGLE_CLIENT_PATH}")
    elif not DEFAULT_GOOGLE_CLIENT_PATH.exists():
        raise SystemExit(
            "credentials/google-oauth-client.json 파일이 없습니다. "
            "Google OAuth JSON 파일 경로를 다시 확인하세요."
        )

    slack_bot_token = _prompt_required("Slack Bot Token을 붙여넣으세요. xoxb- 로 시작합니다")
    if not slack_bot_token.startswith("xoxb-"):
        print("경고: Slack Bot Token은 보통 xoxb- 로 시작합니다.")

    slack_user_id = _prompt_required("내 Slack User ID를 붙여넣으세요. U 로 시작합니다")
    if not slack_user_id.startswith("U"):
        print("경고: Slack User ID는 보통 U 로 시작합니다.")

    poll_interval = _prompt("몇 초마다 Gmail을 확인할까요?", "60")
    max_thread_messages = _prompt("새 thread를 처음 만들 때 최대 몇 개 메일까지 가져올까요?", "30")
    fetch_limit = _prompt("초기 기준점이 없을 때 최근 몇 개를 확인할까요?", "50")

    ENV_PATH.write_text(
        "\n".join(
            [
                "GMAIL_AUTH_MODE=oauth",
                "GOOGLE_CLIENT_SECRET_FILE=credentials/google-oauth-client.json",
                "GOOGLE_TOKEN_FILE=data/google-token.json",
                "GMAIL_QUERY=",
                "",
                f"SLACK_BOT_TOKEN={slack_bot_token}",
                "SLACK_CHANNEL_ID=",
                f"SLACK_USER_ID={slack_user_id}",
                "",
                "GMAIL_BACKFILL_THREADS=false",
                "GMAIL_BACKFILL_ON_FIRST_SEEN_THREAD=true",
                f"GMAIL_MAX_THREAD_MESSAGES={max_thread_messages}",
                "BOOTSTRAP_EXISTING_MESSAGES=true",
                "",
                f"POLL_INTERVAL_SECONDS={poll_interval}",
                f"FETCH_LIMIT={fetch_limit}",
                "DATABASE_PATH=data/mirror.sqlite3",
                "LOG_FILE=logs/gmail-chat.log",
                "LOG_LEVEL=INFO",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print()
    print("설정 완료: .env")
    print("다음 단계로 Gmail 연결을 진행하세요.")


def _prompt(label: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _prompt_required(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print("값이 필요합니다.")


def _clean_path(value: str) -> str:
    return value.strip().strip('"').strip("'")


if __name__ == "__main__":
    main()

