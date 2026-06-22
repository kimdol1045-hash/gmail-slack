from __future__ import annotations

from dataclasses import dataclass
import imaplib
import re


@dataclass(frozen=True)
class RawGmailMessage:
    uid: str
    gmail_thread_id: str
    raw_bytes: bytes


class GmailClient:
    def __init__(
        self,
        *,
        email_address: str,
        app_password: str,
        mailbox: str = "[Gmail]/All Mail",
        host: str = "imap.gmail.com",
        port: int = 993,
    ) -> None:
        self.email_address = email_address
        self.app_password = app_password
        self.mailbox = mailbox
        self.host = host
        self.port = port
        self._imap: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "GmailClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def connect(self) -> None:
        self._imap = imaplib.IMAP4_SSL(self.host, self.port)
        self._check(self._imap.login(self.email_address, self.app_password), "login")

    def close(self) -> None:
        if self._imap is None:
            return
        try:
            self._imap.close()
        except imaplib.IMAP4.error:
            pass
        finally:
            self._imap.logout()
            self._imap = None

    def list_mailboxes(self) -> list[str]:
        imap = self._require_imap()
        status, data = imap.list()
        self._check((status, data), "list mailboxes")
        return [item.decode("utf-8", errors="replace") for item in data if item]

    def select_mailbox(self) -> None:
        imap = self._require_imap()
        mailbox = _quote_mailbox(self.mailbox)
        self._check(imap.select(mailbox, readonly=True), f"select {self.mailbox}")

    def fetch_recent(self, limit: int) -> list[RawGmailMessage]:
        imap = self._require_imap()
        self.select_mailbox()

        status, data = imap.uid("search", None, "ALL")
        self._check((status, data), "search messages")
        uid_bytes = data[0] if data else b""
        uids = uid_bytes.split()
        selected_uids = uids[-limit:] if limit > 0 else uids

        messages: list[RawGmailMessage] = []
        for uid in selected_uids:
            status, fetch_data = imap.uid("fetch", uid, "(X-GM-THRID RFC822)")
            self._check((status, fetch_data), f"fetch uid {uid.decode()}")
            raw_message = self._parse_fetch_response(uid.decode(), fetch_data)
            if raw_message is not None:
                messages.append(raw_message)
        return messages

    def _parse_fetch_response(
        self,
        uid: str,
        fetch_data: list[bytes | tuple[bytes, bytes]],
    ) -> RawGmailMessage | None:
        raw_bytes: bytes | None = None
        metadata_chunks: list[bytes] = []

        for item in fetch_data:
            if isinstance(item, tuple):
                metadata_chunks.append(item[0])
                raw_bytes = item[1]
            elif isinstance(item, bytes):
                metadata_chunks.append(item)

        if raw_bytes is None:
            return None

        metadata = b" ".join(metadata_chunks)
        match = re.search(rb"X-GM-THRID\s+(\d+)", metadata)
        gmail_thread_id = match.group(1).decode("ascii") if match else ""

        return RawGmailMessage(
            uid=uid,
            gmail_thread_id=gmail_thread_id,
            raw_bytes=raw_bytes,
        )

    def _require_imap(self) -> imaplib.IMAP4_SSL:
        if self._imap is None:
            raise RuntimeError("GmailClient is not connected")
        return self._imap

    @staticmethod
    def _check(result: tuple[str, list[bytes] | list[tuple[bytes, bytes]]], action: str) -> None:
        status = result[0]
        if status != "OK":
            raise RuntimeError(f"Gmail IMAP {action} failed: {result!r}")


def _quote_mailbox(mailbox: str) -> str:
    if mailbox.startswith('"') and mailbox.endswith('"'):
        return mailbox
    escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
