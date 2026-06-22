from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Config:
    gmail_email: str
    gmail_auth_mode: str
    gmail_app_password: str
    gmail_mailbox: str
    google_client_secret_file: str
    google_token_file: str
    gmail_query: str
    gmail_backfill_threads: bool
    gmail_backfill_on_first_seen_thread: bool
    gmail_max_thread_messages: int
    bootstrap_existing_messages: bool
    slack_bot_token: str
    slack_channel_id: str
    slack_user_id: str
    poll_interval_seconds: int
    fetch_limit: int
    database_path: str
    log_file: str
    log_level: str


def load_config(
    *,
    require_gmail: bool = False,
    require_slack: bool = False,
    env_path: str | Path = ".env",
) -> Config:
    load_dotenv(env_path)

    config = Config(
        gmail_email=os.getenv("GMAIL_EMAIL", "").strip(),
        gmail_auth_mode=os.getenv("GMAIL_AUTH_MODE", "app_password").strip().lower(),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", "").strip(),
        gmail_mailbox=os.getenv("GMAIL_MAILBOX", "[Gmail]/All Mail").strip(),
        google_client_secret_file=os.getenv(
            "GOOGLE_CLIENT_SECRET_FILE",
            "credentials/google-oauth-client.json",
        ).strip(),
        google_token_file=os.getenv("GOOGLE_TOKEN_FILE", "data/google-token.json").strip(),
        gmail_query=os.getenv("GMAIL_QUERY", "").strip(),
        gmail_backfill_threads=_bool_env("GMAIL_BACKFILL_THREADS", False),
        gmail_backfill_on_first_seen_thread=_bool_env(
            "GMAIL_BACKFILL_ON_FIRST_SEEN_THREAD",
            True,
        ),
        gmail_max_thread_messages=_int_env("GMAIL_MAX_THREAD_MESSAGES", 30),
        bootstrap_existing_messages=_bool_env("BOOTSTRAP_EXISTING_MESSAGES", True),
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
        slack_channel_id=os.getenv("SLACK_CHANNEL_ID", "").strip(),
        slack_user_id=os.getenv("SLACK_USER_ID", "").strip(),
        poll_interval_seconds=_int_env("POLL_INTERVAL_SECONDS", 60),
        fetch_limit=_int_env("FETCH_LIMIT", 50),
        database_path=os.getenv("DATABASE_PATH", "data/mirror.sqlite3").strip(),
        log_file=os.getenv("LOG_FILE", "logs/gmail-chat.log").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )

    missing: list[str] = []
    if require_gmail:
        if config.gmail_auth_mode not in {"app_password", "oauth"}:
            missing.append("GMAIL_AUTH_MODE(app_password|oauth)")
        if config.gmail_auth_mode == "app_password":
            if not config.gmail_email:
                missing.append("GMAIL_EMAIL")
            if not config.gmail_app_password:
                missing.append("GMAIL_APP_PASSWORD")
        if config.gmail_auth_mode == "oauth" and not config.google_client_secret_file:
            missing.append("GOOGLE_CLIENT_SECRET_FILE")
    if require_slack:
        if not config.slack_bot_token:
            missing.append("SLACK_BOT_TOKEN")
        if not config.slack_channel_id and not config.slack_user_id:
            missing.append("SLACK_CHANNEL_ID or SLACK_USER_ID")

    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment values: {names}")

    return config


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")
