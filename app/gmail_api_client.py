from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64

from app.gmail_client import RawGmailMessage


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass(frozen=True)
class OAuthPaths:
    client_secret_file: str
    token_file: str


class GmailApiClient:
    def __init__(
        self,
        *,
        client_secret_file: str,
        token_file: str,
        query: str = "",
    ) -> None:
        self.paths = OAuthPaths(
            client_secret_file=client_secret_file,
            token_file=token_file,
        )
        self.query = query
        self._service = None

    def __enter__(self) -> "GmailApiClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._service = None

    def connect(self) -> None:
        self._service = _build_gmail_service(self.paths)

    def fetch_recent(self, limit: int) -> list[RawGmailMessage]:
        service = self._require_service()
        request = {
            "userId": "me",
            "maxResults": limit,
            "includeSpamTrash": False,
        }
        if self.query:
            request["q"] = self.query

        response = service.users().messages().list(**request).execute()
        messages = response.get("messages", [])
        raw_messages: list[RawGmailMessage] = []

        # Gmail API returns newest-first. Process oldest-first for cleaner Slack threads.
        for message_ref in reversed(messages):
            message_id = message_ref["id"]
            message = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="raw")
                .execute()
            )
            raw_messages.append(
                RawGmailMessage(
                    uid=message["id"],
                    gmail_thread_id=message.get("threadId", ""),
                    raw_bytes=_decode_gmail_raw(message["raw"]),
                )
            )

        return raw_messages

    def fetch_thread(
        self,
        gmail_thread_id: str,
        *,
        max_messages: int = 50,
    ) -> list[RawGmailMessage]:
        service = self._require_service()
        thread = (
            service.users()
            .threads()
            .get(userId="me", id=gmail_thread_id, format="metadata")
            .execute()
        )
        message_refs = thread.get("messages", [])
        if max_messages > 0:
            message_refs = message_refs[-max_messages:]

        raw_messages: list[RawGmailMessage] = []
        for message_ref in message_refs:
            message_id = message_ref["id"]
            message = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="raw")
                .execute()
            )
            raw_messages.append(
                RawGmailMessage(
                    uid=message["id"],
                    gmail_thread_id=message.get("threadId", gmail_thread_id),
                    raw_bytes=_decode_gmail_raw(message["raw"]),
                )
            )

        return raw_messages

    def profile_email(self) -> str:
        service = self._require_service()
        profile = service.users().getProfile(userId="me").execute()
        return str(profile.get("emailAddress", ""))

    def _require_service(self):
        if self._service is None:
            raise RuntimeError("GmailApiClient is not connected")
        return self._service


def authorize_oauth(paths: OAuthPaths) -> None:
    _build_gmail_service(paths)


def _build_gmail_service(paths: OAuthPaths):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google OAuth dependencies are not installed. Run: "
            "python3 -m pip install -r requirements.txt"
        ) from exc

    token_path = Path(paths.token_file)
    client_secret_path = Path(paths.client_secret_file)
    scopes = [GMAIL_READONLY_SCOPE]

    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not client_secret_path.exists():
            raise RuntimeError(
                f"Google OAuth client secret file not found: {client_secret_path}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
        credentials = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=credentials)


def _decode_gmail_raw(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)
