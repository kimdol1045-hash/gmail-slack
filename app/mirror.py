from __future__ import annotations

from datetime import datetime, timezone
import logging
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from app import db
from app.config import Config
from app.gmail_api_client import GmailApiClient
from app.gmail_client import GmailClient, RawGmailMessage
from app.mail_parser import ParsedEmail, parse_email
from app.slack_client import SlackPoster


LOGGER = logging.getLogger(__name__)
GMAIL_HISTORY_STATE_KEY = "gmail_history_id"
DISPLAY_TIMEZONE = ZoneInfo("Asia/Seoul")


class MirrorService:
    def __init__(self, config: Config) -> None:
        self.config = config

    def init_db(self) -> None:
        with db.connect(self.config.database_path) as connection:
            db.init_db(connection)

    def bootstrap_existing(self, *, limit: int | None = None) -> int:
        fetch_limit = limit if limit is not None else self.config.fetch_limit

        with db.connect(self.config.database_path) as connection:
            db.init_db(connection)
            raw_messages, my_email, latest_history_id = self._fetch_raw_messages(
                connection,
                fetch_limit,
            )
            if latest_history_id:
                db.set_state(
                    connection,
                    key=GMAIL_HISTORY_STATE_KEY,
                    value=latest_history_id,
                    updated_at=_now(),
                )
            return self._mark_existing_messages(connection, raw_messages, my_email)

    def seed_recent_threads(self, *, limit: int = 30) -> int:
        if self.config.gmail_auth_mode != "oauth":
            raise RuntimeError("seed_recent_threads is only supported in Gmail OAuth mode")

        posted_count = 0
        with db.connect(self.config.database_path) as connection:
            db.init_db(connection)
            slack = SlackPoster(
                bot_token=self.config.slack_bot_token,
                channel_id=self.config.slack_channel_id,
                user_id=self.config.slack_user_id,
            )

            with GmailApiClient(
                client_secret_file=self.config.google_client_secret_file,
                token_file=self.config.google_token_file,
                query=self.config.gmail_query,
            ) as gmail:
                my_email = self.config.gmail_email or gmail.profile_email()
                thread_ids = gmail.fetch_recent_thread_ids(limit)
                for thread_id in reversed(thread_ids):
                    if db.get_thread(connection, thread_id) is not None:
                        continue
                    raw_messages = gmail.fetch_thread(
                        thread_id,
                        max_messages=self.config.gmail_max_thread_messages,
                    )
                    posted_count += self._mirror_raw_messages(
                        connection,
                        slack,
                        raw_messages,
                        my_email,
                        allowed_backfill_thread_ids={thread_id},
                    )

                latest_history_id = gmail.profile_history_id()
                if latest_history_id:
                    db.set_state(
                        connection,
                        key=GMAIL_HISTORY_STATE_KEY,
                        value=latest_history_id,
                        updated_at=_now(),
                    )

        return posted_count

    def run_once(self, *, limit: int | None = None) -> int:
        fetch_limit = limit if limit is not None else self.config.fetch_limit
        posted_count = 0

        with db.connect(self.config.database_path) as connection:
            db.init_db(connection)
            if (
                self.config.gmail_auth_mode == "oauth"
                and self.config.bootstrap_existing_messages
                and db.message_count(connection) > 0
                and db.get_state(connection, GMAIL_HISTORY_STATE_KEY) is None
            ):
                latest_history_id = self._current_gmail_history_id()
                if latest_history_id:
                    db.set_state(
                        connection,
                        key=GMAIL_HISTORY_STATE_KEY,
                        value=latest_history_id,
                        updated_at=_now(),
                    )
                    LOGGER.info(
                        "Initialized Gmail history baseline at %s without Slack posts.",
                        latest_history_id,
                    )
                    return 0

            raw_messages, my_email, latest_history_id = self._fetch_raw_messages(
                connection,
                fetch_limit,
            )
            allowed_backfill_thread_ids: set[str] = set()

            if self.config.bootstrap_existing_messages and db.message_count(connection) == 0:
                bootstrapped_count = self._mark_existing_messages(
                    connection,
                    raw_messages,
                    my_email,
                )
                LOGGER.info(
                    "Bootstrapped %s existing Gmail message(s) without Slack posts.",
                    bootstrapped_count,
                )
                if latest_history_id:
                    db.set_state(
                        connection,
                        key=GMAIL_HISTORY_STATE_KEY,
                        value=latest_history_id,
                        updated_at=_now(),
                    )
                return 0

            if (
                self.config.gmail_auth_mode == "oauth"
                and self.config.gmail_backfill_on_first_seen_thread
                and not self.config.gmail_backfill_threads
            ):
                raw_messages, allowed_backfill_thread_ids = (
                    self._backfill_first_seen_oauth_threads(
                        connection,
                        raw_messages,
                        my_email,
                    )
                )

            slack = SlackPoster(
                bot_token=self.config.slack_bot_token,
                channel_id=self.config.slack_channel_id,
                user_id=self.config.slack_user_id,
            )

            posted_count += self._mirror_raw_messages(
                connection,
                slack,
                raw_messages,
                my_email,
                allowed_backfill_thread_ids=allowed_backfill_thread_ids,
            )

            if latest_history_id:
                db.set_state(
                    connection,
                    key=GMAIL_HISTORY_STATE_KEY,
                    value=latest_history_id,
                    updated_at=_now(),
                )

        return posted_count

    def _mirror_raw_messages(
        self,
        connection,
        slack: SlackPoster,
        raw_messages: list[RawGmailMessage],
        my_email: str,
        *,
        allowed_backfill_thread_ids: set[str],
    ) -> int:
        posted_count = 0
        for raw_message in raw_messages:
            email = parse_email(
                uid=raw_message.uid,
                gmail_thread_id=raw_message.gmail_thread_id,
                raw_bytes=raw_message.raw_bytes,
                my_email=my_email,
            )
            if not email.gmail_thread_id:
                LOGGER.warning("Skipping uid=%s without Gmail thread id", email.uid)
                continue
            if db.has_posted_message(connection, email.message_id):
                continue
            if (
                db.has_message(connection, email.message_id)
                and email.gmail_thread_id not in allowed_backfill_thread_ids
            ):
                continue

            slack_ts = self._mirror_email(connection, slack, email)
            self._save_processed(connection, email, slack_ts, slack.channel_id)
            posted_count += 1

        return posted_count

    def _backfill_first_seen_oauth_threads(
        self,
        connection,
        raw_messages: list[RawGmailMessage],
        my_email: str,
    ) -> tuple[list[RawGmailMessage], set[str]]:
        thread_ids_to_backfill: set[str] = set()

        for raw_message in raw_messages:
            email = parse_email(
                uid=raw_message.uid,
                gmail_thread_id=raw_message.gmail_thread_id,
                raw_bytes=raw_message.raw_bytes,
                my_email=my_email,
            )
            if not email.gmail_thread_id:
                continue
            if db.get_thread(connection, email.gmail_thread_id) is not None:
                continue
            if not db.has_message(connection, email.message_id):
                thread_ids_to_backfill.add(email.gmail_thread_id)

        if not thread_ids_to_backfill:
            return raw_messages, set()

        expanded_messages: list[RawGmailMessage] = []
        expanded_thread_ids: set[str] = set()
        with GmailApiClient(
            client_secret_file=self.config.google_client_secret_file,
            token_file=self.config.google_token_file,
            query=self.config.gmail_query,
        ) as gmail:
            for raw_message in raw_messages:
                thread_id = raw_message.gmail_thread_id
                if thread_id not in thread_ids_to_backfill:
                    expanded_messages.append(raw_message)
                    continue
                if thread_id in expanded_thread_ids:
                    continue

                expanded_thread_ids.add(thread_id)
                try:
                    thread_messages = gmail.fetch_thread(
                        thread_id,
                        max_messages=self.config.gmail_max_thread_messages,
                    )
                except Exception:
                    LOGGER.exception(
                        "Failed to backfill first-seen Gmail thread %s; using fetched message only",
                        thread_id,
                    )
                    thread_messages = [raw_message]
                expanded_messages.extend(thread_messages)

        return _dedupe_raw_messages(expanded_messages), thread_ids_to_backfill

    def _fetch_raw_messages(
        self,
        connection,
        fetch_limit: int,
    ) -> tuple[list[RawGmailMessage], str, str]:
        if self.config.gmail_auth_mode == "oauth":
            with GmailApiClient(
                client_secret_file=self.config.google_client_secret_file,
                token_file=self.config.google_token_file,
                query=self.config.gmail_query,
            ) as gmail:
                my_email = self.config.gmail_email or gmail.profile_email()
                latest_history_id = ""
                start_history_id = db.get_state(connection, GMAIL_HISTORY_STATE_KEY)
                if start_history_id:
                    try:
                        raw_messages, latest_history_id = gmail.fetch_history_since(
                            start_history_id,
                        )
                    except Exception:
                        LOGGER.exception(
                            "Failed to fetch Gmail history since %s; resetting baseline without Slack posts.",
                            start_history_id,
                        )
                        raw_messages = []
                        latest_history_id = gmail.profile_history_id()
                else:
                    raw_messages = gmail.fetch_recent(fetch_limit)
                    latest_history_id = gmail.profile_history_id()

                if self.config.gmail_backfill_threads:
                    raw_messages = self._backfill_oauth_threads(gmail, raw_messages)
        else:
            with GmailClient(
                email_address=self.config.gmail_email,
                app_password=self.config.gmail_app_password,
                mailbox=self.config.gmail_mailbox,
            ) as gmail:
                raw_messages = gmail.fetch_recent(fetch_limit)
                my_email = self.config.gmail_email
                latest_history_id = ""

        return raw_messages, my_email, latest_history_id

    def _current_gmail_history_id(self) -> str:
        if self.config.gmail_auth_mode != "oauth":
            return ""
        with GmailApiClient(
            client_secret_file=self.config.google_client_secret_file,
            token_file=self.config.google_token_file,
            query=self.config.gmail_query,
        ) as gmail:
            return gmail.profile_history_id()

    def _mark_existing_messages(
        self,
        connection,
        raw_messages: list[RawGmailMessage],
        my_email: str,
    ) -> int:
        marked_count = 0
        for raw_message in raw_messages:
            email = parse_email(
                uid=raw_message.uid,
                gmail_thread_id=raw_message.gmail_thread_id,
                raw_bytes=raw_message.raw_bytes,
                my_email=my_email,
            )
            if db.has_message(connection, email.message_id):
                continue
            db.save_message(
                connection,
                message_id=email.message_id,
                gmail_uid=email.uid,
                gmail_thread_id=email.gmail_thread_id,
                slack_channel_id="",
                slack_ts="",
                direction=email.direction,
                subject=email.subject,
                processed_at=_now(),
            )
            marked_count += 1
        return marked_count

    def _backfill_oauth_threads(
        self,
        gmail: GmailApiClient,
        raw_messages: list[RawGmailMessage],
    ) -> list[RawGmailMessage]:
        expanded_messages: list[RawGmailMessage] = []
        expanded_thread_ids: set[str] = set()

        for raw_message in raw_messages:
            if not raw_message.gmail_thread_id:
                expanded_messages.append(raw_message)
                continue

            if raw_message.gmail_thread_id in expanded_thread_ids:
                continue

            expanded_thread_ids.add(raw_message.gmail_thread_id)
            try:
                thread_messages = gmail.fetch_thread(
                    raw_message.gmail_thread_id,
                    max_messages=self.config.gmail_max_thread_messages,
                )
            except Exception:
                LOGGER.exception(
                    "Failed to backfill Gmail thread %s; using fetched message only",
                    raw_message.gmail_thread_id,
                )
                thread_messages = [raw_message]

            expanded_messages.extend(thread_messages)

        return _dedupe_raw_messages(expanded_messages)

    def _mirror_email(
        self,
        connection,
        slack: SlackPoster,
        email: ParsedEmail,
    ) -> str:
        existing_thread = db.get_thread(connection, email.gmail_thread_id)
        if existing_thread is None:
            text = self._format_parent_message(email)
            parent_ts = slack.post_message(text)
            db.save_thread(
                connection,
                gmail_thread_id=email.gmail_thread_id,
                slack_channel_id=slack.channel_id,
                slack_thread_ts=parent_ts,
                subject=email.subject,
                created_at=_now(),
            )
            reply_ts = slack.post_message(
                self._format_reply_message(email, include_date=False),
                thread_ts=parent_ts,
            )
            LOGGER.info(
                "Created Slack thread for Gmail thread %s at %s",
                email.gmail_thread_id,
                parent_ts,
            )
            return reply_ts

        text = self._format_reply_message(email)
        slack_ts = slack.post_message(
            text,
            thread_ts=str(existing_thread["slack_thread_ts"]),
        )
        LOGGER.info(
            "Posted reply for Gmail thread %s at %s",
            email.gmail_thread_id,
            slack_ts,
        )
        return slack_ts

    def _save_processed(
        self,
        connection,
        email: ParsedEmail,
        slack_ts: str,
        slack_channel_id: str,
    ) -> None:
        db.save_message(
            connection,
            message_id=email.message_id,
            gmail_uid=email.uid,
            gmail_thread_id=email.gmail_thread_id,
            slack_channel_id=slack_channel_id,
            slack_ts=slack_ts,
            direction=email.direction,
            subject=email.subject,
            processed_at=_now(),
        )

    @staticmethod
    def _format_parent_message(email: ParsedEmail) -> str:
        return (
            f"*{email.subject}*\n"
            f"*From:* {_display_sender(email)}\n"
            f"*Date:* {_display_date(email.date)}"
        )

    @staticmethod
    def _format_reply_message(email: ParsedEmail, *, include_date: bool = True) -> str:
        body = email.body or "(empty body)"
        direction = "OUT" if email.direction == "outbound" else "IN"
        quoted_body = _quote_body(body)
        parts = [f"*[{direction}] {_display_sender(email)}*"]
        if include_date:
            parts.append(f"`{_display_date(email.date)}`")
        parts.append(quoted_body)
        return "\n".join(parts)


def _display_sender(email: ParsedEmail) -> str:
    return "Me" if email.direction == "outbound" else email.sender


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except Exception:
            return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=DISPLAY_TIMEZONE)
    else:
        parsed = parsed.astimezone(DISPLAY_TIMEZONE)
    meridiem = "오전" if parsed.hour < 12 else "오후"
    hour = parsed.hour % 12
    if hour == 0:
        hour = 12
    minute = f"{parsed.minute:02d}"
    return f"{parsed.year}년 {parsed.month}월 {parsed.day}일 {meridiem} {hour}:{minute}"


def _quote_body(body: str) -> str:
    lines = body.strip().splitlines()
    if not lines:
        return "> (empty body)"
    return "\n".join(f"> {line}" if line.strip() else ">" for line in lines)


def _dedupe_raw_messages(messages: list[RawGmailMessage]) -> list[RawGmailMessage]:
    deduped: list[RawGmailMessage] = []
    seen_uids: set[str] = set()
    for message in messages:
        if message.uid in seen_uids:
            continue
        seen_uids.add(message.uid)
        deduped.append(message)
    return deduped
