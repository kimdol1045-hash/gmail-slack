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

    def test_clean_body_keeps_gmail_forwarded_body_after_signature(self) -> None:
        body = (
            "이찬두 이사 ㅣ 상품개발그룹\n\n"
            "(주) 셀메이트\n\n"
            "전화 070-8680-6433  모바일 010-5044-0912 이메일 dooricg@sellmate.co.kr\n\n"
            "주소 서울시 마포구 만리재로47, 공덕코어빌딩 3,5,10,11층\n\n"
            "---------- Forwarded message ---------\n"
            "보낸사람: 이찬두 <dooricg@sellmate.co.kr>\n"
            "Date: 2026년 6월 25일 (목) 오후 4:58\n"
            "Subject: Re: [개발요청] 다수 송장 배송추적 관리 화면(메뉴) 신규 개발 요청\n"
            "To: 김중훈 <KJHS@yongmalogis.co.kr>\n"
            "Cc: 김광석 <kks@sellmate.co.kr>\n\n"
            "안녕하세요 책임님\n"
            "셀메이트 이찬두 입니다.\n\n"
            "내용은 어제 광석님 통해 전달 받았습니다.\n\n"
            "2026년 6월 25일 (목) 오후 4:19, 김중훈 <KJHS@yongmalogis.co.kr>님이 작성:\n"
            "> 이전 메일 내용\n"
        )

        self.assertEqual(
            clean_body(body),
            "안녕하세요 책임님\n셀메이트 이찬두 입니다.\n\n내용은 어제 광석님 통해 전달 받았습니다.",
        )

    def test_clean_body_keeps_forward_intro_with_forwarded_body(self) -> None:
        body = (
            "확인 부탁드립니다.\n\n"
            "---------- Forwarded message ---------\n"
            "From: Alice <alice@example.com>\n"
            "Date: Thu, 25 Jun 2026 10:00:00 +0900\n"
            "Subject: Original request\n"
            "To: Me <me@example.com>\n\n"
            "Forwarded request body."
        )

        self.assertEqual(
            clean_body(body),
            "확인 부탁드립니다.\n\nForwarded request body.",
        )

    def test_clean_body_keeps_forward_intro_with_title_word(self) -> None:
        body = (
            "이사님 확인 부탁드립니다.\n\n"
            "---------- Forwarded message ---------\n"
            "From: Alice <alice@example.com>\n\n"
            "Forwarded request body."
        )

        self.assertEqual(
            clean_body(body),
            "이사님 확인 부탁드립니다.\n\nForwarded request body.",
        )


if __name__ == "__main__":
    unittest.main()
