from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import re


@dataclass(frozen=True)
class ParsedEmail:
    uid: str
    message_id: str
    gmail_thread_id: str
    subject: str
    sender: str
    sender_email: str
    recipients: list[str]
    date: str
    direction: str
    body: str


def parse_email(
    *,
    uid: str,
    gmail_thread_id: str,
    raw_bytes: bytes,
    my_email: str,
) -> ParsedEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    message_id = _header(message, "Message-ID")
    subject = _header(message, "Subject") or "(no subject)"
    sender = _header(message, "From") or "(unknown sender)"
    sender_email = _first_email(sender)
    recipients = [_email for _, _email in getaddresses(message.get_all("To", [])) if _email]
    date = _message_date(message)
    direction = "outbound" if sender_email.lower() == my_email.lower() else "inbound"
    body = clean_body(extract_body(message))

    return ParsedEmail(
        uid=uid,
        message_id=message_id or f"uid:{uid}",
        gmail_thread_id=gmail_thread_id,
        subject=subject,
        sender=sender,
        sender_email=sender_email,
        recipients=recipients,
        date=date,
        direction=direction,
        body=body,
    )


def extract_body(message: Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                continue
            content_type = part.get_content_type()
            text = _part_text(part)
            if not text:
                continue
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(html_to_text(text))
    else:
        content_type = message.get_content_type()
        text = _part_text(message)
        if content_type == "text/html":
            html_parts.append(html_to_text(text))
        elif text:
            plain_parts.append(text)

    if plain_parts:
        return "\n\n".join(plain_parts)
    return "\n\n".join(html_parts)


def clean_body(text: str) -> str:
    normalized = normalize_whitespace(text)
    if not normalized:
        return ""

    forwarded_cleaned = _clean_forwarded_message(normalized)
    if forwarded_cleaned:
        return forwarded_cleaned

    talon_cleaned = _talon_extract(normalized)
    if talon_cleaned:
        normalized = talon_cleaned

    return strip_basic_quotes(normalized).strip()


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_basic_quotes(text: str) -> str:
    kept_lines: list[str] = []
    quote_markers = (
        "-----Original Message-----",
        "----- Forwarded message -----",
        "Begin forwarded message:",
        "---------- 원본 메일 ----------",
        "원본 메일",
    )

    for line in text.splitlines():
        stripped = line.strip()
        if stripped in quote_markers or _is_forwarded_marker(stripped):
            break
        if re.match(r"^[_-]{8,}$", stripped):
            break
        if re.match(r"^On .+ wrote:$", stripped):
            break
        if re.match(r"^.+ 작성:$", stripped):
            break
        if re.match(r"^(From|Sent|To|Cc|Subject):\s*", stripped, flags=re.IGNORECASE):
            break
        if re.match(r"^(보낸사람|보낸시간|받는사람|참조|제목)\s*:", stripped):
            break
        if stripped.startswith(">"):
            continue
        kept_lines.append(line)

    without_quotes = "\n".join(kept_lines).strip()
    signature_index = without_quotes.find("\n-- \n")
    if signature_index != -1:
        without_quotes = without_quotes[:signature_index]
    return without_quotes.strip()


def _clean_forwarded_message(text: str) -> str:
    lines = text.splitlines()
    marker_index = _forwarded_marker_index(lines)
    if marker_index is None:
        return ""

    preamble = "\n".join(lines[:marker_index]).strip()
    forwarded = "\n".join(lines[marker_index + 1 :]).strip()
    if not forwarded:
        return ""

    forwarded_body = _strip_forwarded_headers(forwarded)
    if not forwarded_body:
        return ""

    forwarded_body = strip_basic_quotes(forwarded_body)
    if not forwarded_body:
        return ""

    preamble = strip_basic_quotes(preamble)
    parts: list[str] = []
    if preamble and not _looks_like_signature_only(preamble):
        parts.append(preamble)
    parts.append(forwarded_body)
    return "\n\n".join(parts).strip()


def _forwarded_marker_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _is_forwarded_marker(line.strip()):
            return index
    return None


def _is_forwarded_marker(line: str) -> bool:
    return bool(re.match(r"^-{2,}\s*Forwarded message\s*-{2,}$", line, re.IGNORECASE))


def _strip_forwarded_headers(text: str) -> str:
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1

    if index >= len(lines) or not _is_forwarded_header_line(lines[index].strip()):
        return text.strip()

    index += 1
    while index < len(lines) and lines[index].strip():
        index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1

    return "\n".join(lines[index:]).strip()


def _is_forwarded_header_line(line: str) -> bool:
    return bool(
        re.match(r"^(From|Sent|To|Cc|Subject|Date):\s*", line, flags=re.IGNORECASE)
        or re.match(r"^(보낸사람|보낸시간|받는사람|참조|제목)\s*:", line)
    )


def _looks_like_signature_only(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > 8:
        return False

    signature_lines = 0
    hard_signature_lines = 0
    for line in lines:
        if _is_signature_line(line):
            signature_lines += 1
        if _is_hard_signature_line(line):
            hard_signature_lines += 1

    return signature_lines == len(lines) and hard_signature_lines > 0


def _is_signature_line(line: str) -> bool:
    return bool(
        _is_hard_signature_line(line)
        or re.search(r"(이사|대표|팀장|책임|그룹|팀|부서|Manager|Director)", line, re.IGNORECASE)
        or line == "--"
    )


def _is_hard_signature_line(line: str) -> bool:
    return bool(
        "@" in line
        or re.search(r"\b\d{2,4}-\d{3,4}-\d{4}\b", line)
        or re.search(r"(전화|모바일|이메일|주소|Tel|Phone|Mobile|Fax)", line, re.IGNORECASE)
        or re.search(r"(\(주\)|주식회사|Inc\.?|Ltd\.?|Corp\.?|Company)", line, re.IGNORECASE)
    )


def html_to_text(html: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(html)
    return normalize_whitespace(parser.text())


def _talon_extract(text: str) -> str:
    try:
        from talon import quotations
    except Exception:
        return ""

    try:
        cleaned = quotations.extract_from(text, "text/plain")
    except Exception:
        return ""
    return normalize_whitespace(cleaned)


def _part_text(part: Message) -> str:
    try:
        if isinstance(part, EmailMessage):
            content = part.get_content()
            return content if isinstance(content, str) else ""
    except Exception:
        pass

    payload = part.get_payload(decode=True)
    if payload is None:
        raw_payload = part.get_payload()
        return raw_payload if isinstance(raw_payload, str) else ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _header(message: Message, name: str) -> str:
    value = message.get(name, "")
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def _first_email(address_header: str) -> str:
    addresses = getaddresses([address_header])
    if not addresses:
        return ""
    return addresses[0][1]


def _message_date(message: Message) -> str:
    raw_date = _header(message, "Date")
    if not raw_date:
        return ""
    try:
        return parsedate_to_datetime(raw_date).isoformat()
    except Exception:
        return raw_date


class _TextHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "blockquote",
        "br",
        "div",
        "li",
        "p",
        "table",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        joined = "".join(self._chunks)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n[ \t]+", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()
