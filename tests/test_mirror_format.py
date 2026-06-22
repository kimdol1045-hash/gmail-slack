from __future__ import annotations

import unittest

from app.mail_parser import ParsedEmail
from app.mirror import MirrorService


class MirrorFormatTest(unittest.TestCase):
    def test_parent_message_is_subject_only(self) -> None:
        email = ParsedEmail(
            uid="1",
            message_id="<msg@example.com>",
            gmail_thread_id="thread-1",
            subject="Re: Important thread",
            sender="Alice <alice@example.com>",
            sender_email="alice@example.com",
            recipients=[],
            date="2026-06-19T10:00:00+09:00",
            direction="inbound",
            body="This belongs in a Slack reply.",
        )

        self.assertEqual(
            MirrorService._format_parent_message(email),
            "*Re: Important thread*\nFrom: Alice <alice@example.com>",
        )
        reply = MirrorService._format_reply_message(email)
        self.assertIn("*[IN] Alice <alice@example.com>*", reply)
        self.assertIn("`2026년 6월 19일 오전 10:00`", reply)
        self.assertIn("> This belongs in a Slack reply.", reply)


if __name__ == "__main__":
    unittest.main()
