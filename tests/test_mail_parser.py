from __future__ import annotations

import unittest

from app.mail_parser import clean_body, parse_email


class MailParserTest(unittest.TestCase):
    def test_parse_plain_text_email(self) -> None:
        raw = (
            b"From: Alice <alice@example.com>\r\n"
            b"To: Me <me@example.com>\r\n"
            b"Subject: Contract review\r\n"
            b"Message-ID: <msg-1@example.com>\r\n"
            b"Date: Fri, 19 Jun 2026 10:00:00 +0900\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Please review this contract.\r\n"
            b"\r\n"
            b"On Fri, Bob wrote:\r\n"
            b"> previous message\r\n"
        )

        parsed = parse_email(
            uid="123",
            gmail_thread_id="456",
            raw_bytes=raw,
            my_email="me@example.com",
        )

        self.assertEqual(parsed.message_id, "<msg-1@example.com>")
        self.assertEqual(parsed.gmail_thread_id, "456")
        self.assertEqual(parsed.direction, "inbound")
        self.assertEqual(parsed.subject, "Contract review")
        self.assertEqual(parsed.body, "Please review this contract.")

    def test_outbound_direction(self) -> None:
        raw = (
            b"From: Me <me@example.com>\r\n"
            b"To: Alice <alice@example.com>\r\n"
            b"Subject: Re: Contract review\r\n"
            b"Date: Fri, 19 Jun 2026 10:10:00 +0900\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Looks good to me.\r\n"
        )

        parsed = parse_email(
            uid="124",
            gmail_thread_id="456",
            raw_bytes=raw,
            my_email="me@example.com",
        )

        self.assertEqual(parsed.direction, "outbound")
        self.assertEqual(parsed.message_id, "uid:124")
        self.assertEqual(parsed.body, "Looks good to me.")

    def test_clean_body_removes_signature(self) -> None:
        body = "Thanks.\n-- \nAlice\nCompany"

        self.assertEqual(clean_body(body), "Thanks.")

    def test_clean_body_removes_korean_outlook_quote(self) -> None:
        body = (
            "안녕하세요.\n확인했습니다.\n\n"
            "________________________________\n"
            "보낸사람:정상건[sgjung@sellmate.co.kr]\n"
            "보낸시간:2026년 6월 19일 금요일 오후 12:01:39\n"
            "제목:Re: 이전 메일\n\n"
            "이전 메일 내용"
        )

        self.assertEqual(clean_body(body), "안녕하세요.\n확인했습니다.")

    def test_clean_body_removes_original_mail_marker(self) -> None:
        body = (
            "새 의견입니다.\n\n"
            "---------- 원본 메일 ----------\n"
            "보낸사람: someone@example.com\n"
            "이전 메일"
        )

        self.assertEqual(clean_body(body), "새 의견입니다.")


if __name__ == "__main__":
    unittest.main()
