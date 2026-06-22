from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from app import db
from app.config import Config
from app.gmail_client import RawGmailMessage
import app.mirror as mirror_module
from app.mirror import MirrorService


def _raw_email(message_id: str, subject: str = "Re: Thread A") -> bytes:
    return (
        f"From: Alice <alice@example.com>\r\n"
        f"To: Me <me@example.com>\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"Date: Fri, 19 Jun 2026 10:00:00 +0900\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"Body for {message_id}\r\n"
    ).encode("utf-8")


class FakeGmailApiClient:
    thread_messages: list[RawGmailMessage] = []

    def __init__(self, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def fetch_thread(self, gmail_thread_id: str, *, max_messages: int = 30):
        return self.thread_messages[-max_messages:]


class FirstSeenBackfillTest(unittest.TestCase):
    def test_backfills_thread_only_when_new_message_appears(self) -> None:
        existing = RawGmailMessage(
            uid="gmail-1",
            gmail_thread_id="thread-a",
            raw_bytes=_raw_email("<msg-1@example.com>"),
        )
        new = RawGmailMessage(
            uid="gmail-2",
            gmail_thread_id="thread-a",
            raw_bytes=_raw_email("<msg-2@example.com>"),
        )
        FakeGmailApiClient.thread_messages = [existing, new]

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "mirror.sqlite3")
            service = MirrorService(_config(database_path))
            original_client = mirror_module.GmailApiClient
            mirror_module.GmailApiClient = FakeGmailApiClient
            try:
                with db.connect(database_path) as connection:
                    db.init_db(connection)
                    db.save_message(
                        connection,
                        message_id="<msg-1@example.com>",
                        gmail_uid="gmail-1",
                        gmail_thread_id="thread-a",
                        slack_channel_id="",
                        slack_ts="",
                        direction="inbound",
                        subject="Re: Thread A",
                        processed_at=datetime.now(timezone.utc).isoformat(),
                    )

                    expanded, allowed = service._backfill_first_seen_oauth_threads(
                        connection,
                        [new],
                        "me@example.com",
                    )
            finally:
                mirror_module.GmailApiClient = original_client

        self.assertEqual([message.uid for message in expanded], ["gmail-1", "gmail-2"])
        self.assertEqual(allowed, {"thread-a"})

    def test_does_not_backfill_when_only_bootstrapped_messages_are_seen(self) -> None:
        existing = RawGmailMessage(
            uid="gmail-1",
            gmail_thread_id="thread-a",
            raw_bytes=_raw_email("<msg-1@example.com>"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "mirror.sqlite3")
            service = MirrorService(_config(database_path))
            with db.connect(database_path) as connection:
                db.init_db(connection)
                db.save_message(
                    connection,
                    message_id="<msg-1@example.com>",
                    gmail_uid="gmail-1",
                    gmail_thread_id="thread-a",
                    slack_channel_id="",
                    slack_ts="",
                    direction="inbound",
                    subject="Re: Thread A",
                    processed_at=datetime.now(timezone.utc).isoformat(),
                )

                expanded, allowed = service._backfill_first_seen_oauth_threads(
                    connection,
                    [existing],
                    "me@example.com",
                )

        self.assertEqual([message.uid for message in expanded], ["gmail-1"])
        self.assertEqual(allowed, set())


def _config(database_path: str) -> Config:
    return Config(
        gmail_email="me@example.com",
        gmail_auth_mode="oauth",
        gmail_app_password="",
        gmail_mailbox="[Gmail]/All Mail",
        google_client_secret_file="credentials/google-oauth-client.json",
        google_token_file="data/google-token.json",
        gmail_query="",
        gmail_backfill_threads=False,
        gmail_backfill_on_first_seen_thread=True,
        gmail_max_thread_messages=30,
        bootstrap_existing_messages=True,
        slack_bot_token="xoxb-test",
        slack_channel_id="",
        slack_user_id="U123",
        poll_interval_seconds=60,
        fetch_limit=5,
        database_path=database_path,
        log_file="",
        log_level="INFO",
    )


if __name__ == "__main__":
    unittest.main()

