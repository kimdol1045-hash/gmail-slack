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
    thread_ids: list[str] = []
    thread_message_map: dict[str, list[RawGmailMessage]] = {}
    requested_limit: int | None = None

    def __init__(self, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def profile_email(self) -> str:
        return "me@example.com"

    def profile_history_id(self) -> str:
        return "history-123"

    def fetch_recent_thread_ids(self, limit: int) -> list[str]:
        self.__class__.requested_limit = limit
        return self.thread_ids

    def fetch_thread(self, gmail_thread_id: str, *, max_messages: int = 30):
        if self.thread_message_map:
            return self.thread_message_map[gmail_thread_id][-max_messages:]
        return self.thread_messages[-max_messages:]


class FakeSlackPoster:
    posted_messages: list[dict[str, str | None]] = []

    def __init__(self, *, bot_token: str, channel_id: str = "", user_id: str = "") -> None:
        self.channel_id = channel_id or "D123"

    def post_message(self, text: str, *, thread_ts: str | None = None) -> str:
        ts = f"ts-{len(self.posted_messages) + 1}"
        self.posted_messages.append(
            {
                "text": text,
                "thread_ts": thread_ts,
                "ts": ts,
            }
        )
        return ts


class FirstSeenBackfillTest(unittest.TestCase):
    def test_backfills_thread_only_when_new_message_appears(self) -> None:
        FakeGmailApiClient.thread_message_map = {}
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


class SeedRecentThreadsTest(unittest.TestCase):
    def test_seeds_recent_threads_and_stores_history_baseline(self) -> None:
        FakeGmailApiClient.thread_ids = ["thread-new", "thread-old"]
        FakeGmailApiClient.thread_message_map = {
            "thread-new": [
                RawGmailMessage(
                    uid="gmail-new-1",
                    gmail_thread_id="thread-new",
                    raw_bytes=_raw_email("<new-1@example.com>", subject="New thread"),
                ),
            ],
            "thread-old": [
                RawGmailMessage(
                    uid="gmail-old-1",
                    gmail_thread_id="thread-old",
                    raw_bytes=_raw_email("<old-1@example.com>", subject="Old thread"),
                ),
                RawGmailMessage(
                    uid="gmail-old-2",
                    gmail_thread_id="thread-old",
                    raw_bytes=_raw_email("<old-2@example.com>", subject="Re: Old thread"),
                ),
            ],
        }
        FakeGmailApiClient.requested_limit = None
        FakeSlackPoster.posted_messages = []

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "mirror.sqlite3")
            service = MirrorService(_config(database_path))
            original_client = mirror_module.GmailApiClient
            original_slack = mirror_module.SlackPoster
            mirror_module.GmailApiClient = FakeGmailApiClient
            mirror_module.SlackPoster = FakeSlackPoster
            try:
                posted_count = service.seed_recent_threads(limit=30)
            finally:
                mirror_module.GmailApiClient = original_client
                mirror_module.SlackPoster = original_slack

            with db.connect(database_path) as connection:
                db.init_db(connection)
                history_id = db.get_state(connection, mirror_module.GMAIL_HISTORY_STATE_KEY)
                old_thread = db.get_thread(connection, "thread-old")
                new_thread = db.get_thread(connection, "thread-new")

        self.assertEqual(posted_count, 3)
        self.assertEqual(FakeGmailApiClient.requested_limit, 30)
        self.assertEqual(history_id, "history-123")
        self.assertIsNotNone(old_thread)
        self.assertIsNotNone(new_thread)

        old_parent_text = (
            "*Old thread*\n"
            "*From:* Alice <alice@example.com>\n"
            "*Date:* 2026년 6월 19일 오전 10:00"
        )
        new_parent_text = (
            "*New thread*\n"
            "*From:* Alice <alice@example.com>\n"
            "*Date:* 2026년 6월 19일 오전 10:00"
        )
        self.assertEqual(FakeSlackPoster.posted_messages[0]["text"], old_parent_text)
        self.assertEqual(FakeSlackPoster.posted_messages[1]["thread_ts"], "ts-1")
        self.assertIn(
            "> Body for <old-1@example.com>",
            str(FakeSlackPoster.posted_messages[1]["text"]),
        )
        self.assertEqual(FakeSlackPoster.posted_messages[2]["thread_ts"], "ts-1")
        self.assertIn(
            "`2026년 6월 19일 오전 10:00`",
            str(FakeSlackPoster.posted_messages[2]["text"]),
        )
        self.assertEqual(FakeSlackPoster.posted_messages[3]["text"], new_parent_text)


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
