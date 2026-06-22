from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from app import db


class DbTest(unittest.TestCase):
    def test_thread_and_message_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "mirror.sqlite3")
            now = datetime.now(timezone.utc).isoformat()

            with db.connect(database_path) as connection:
                db.init_db(connection)
                db.save_thread(
                    connection,
                    gmail_thread_id="gmail-thread-1",
                    slack_channel_id="C123",
                    slack_thread_ts="1710000000.000100",
                    subject="Hello",
                    created_at=now,
                )
                db.save_message(
                    connection,
                    message_id="<msg-1@example.com>",
                    gmail_uid="1",
                    gmail_thread_id="gmail-thread-1",
                    slack_channel_id="C123",
                    slack_ts="1710000000.000200",
                    direction="inbound",
                    subject="Hello",
                    processed_at=now,
                )

                thread = db.get_thread(connection, "gmail-thread-1")

                self.assertIsNotNone(thread)
                self.assertEqual(thread["slack_thread_ts"], "1710000000.000100")
                self.assertTrue(db.has_message(connection, "<msg-1@example.com>"))
                self.assertTrue(db.has_posted_message(connection, "<msg-1@example.com>"))
                self.assertFalse(db.has_message(connection, "<msg-2@example.com>"))

                db.save_message(
                    connection,
                    message_id="<msg-1@example.com>",
                    gmail_uid="1",
                    gmail_thread_id="gmail-thread-1",
                    slack_channel_id="",
                    slack_ts="",
                    direction="inbound",
                    subject="Hello",
                    processed_at=now,
                )

                self.assertFalse(db.has_posted_message(connection, "<msg-1@example.com>"))


if __name__ == "__main__":
    unittest.main()
