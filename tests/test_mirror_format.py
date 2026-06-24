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
            "*Re: Important thread*\n"
            "*From:* Alice <alice@example.com>\n"
            "*Date:* 2026년 6월 19일 오전 10:00",
        )
        reply = MirrorService._format_reply_message(email)
        self.assertIn("*[IN] Alice <alice@example.com>*", reply)
        self.assertIn("`2026년 6월 19일 오전 10:00`", reply)
        self.assertIn("> This belongs in a Slack reply.", reply)

    def test_first_reply_can_omit_date(self) -> None:
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
            body="First message body.",
        )

        reply = MirrorService._format_reply_message(email, include_date=False)

        self.assertIn("*[IN] Alice <alice@example.com>*", reply)
        self.assertNotIn("2026년", reply)
        self.assertIn("> First message body.", reply)

    def test_utc_date_is_displayed_in_seoul_time(self) -> None:
        email = ParsedEmail(
            uid="1",
            message_id="<msg@example.com>",
            gmail_thread_id="thread-1",
            subject="Re: Important thread",
            sender="Alice <alice@example.com>",
            sender_email="alice@example.com",
            recipients=[],
            date="2026-06-24T07:03:00+00:00",
            direction="inbound",
            body="Body.",
        )

        self.assertIn(
            "*Date:* 2026년 6월 24일 오후 4:03",
            MirrorService._format_parent_message(email),
        )


if __name__ == "__main__":
    unittest.main()
