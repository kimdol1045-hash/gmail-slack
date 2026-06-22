from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA = """
create table if not exists threads (
  gmail_thread_id text primary key,
  slack_channel_id text not null,
  slack_thread_ts text not null,
  subject text,
  created_at text not null
);

create table if not exists messages (
  message_id text primary key,
  gmail_uid text,
  gmail_thread_id text not null,
  slack_channel_id text not null,
  slack_ts text,
  direction text not null,
  subject text,
  processed_at text not null
);

create index if not exists idx_messages_thread
  on messages(gmail_thread_id);

create table if not exists state (
  key text primary key,
  value text not null,
  updated_at text not null
);
"""


@contextmanager
def connect(database_path: str) -> Iterator[sqlite3.Connection]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def has_message(connection: sqlite3.Connection, message_id: str) -> bool:
    row = connection.execute(
        "select 1 from messages where message_id = ?",
        (message_id,),
    ).fetchone()
    return row is not None


def has_posted_message(connection: sqlite3.Connection, message_id: str) -> bool:
    row = connection.execute(
        """
        select 1
        from messages
        where message_id = ?
          and slack_ts is not null
          and slack_ts != ''
        """,
        (message_id,),
    ).fetchone()
    return row is not None


def message_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("select count(*) as count from messages").fetchone()
    return int(row["count"])


def get_state(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute(
        "select value from state where key = ?",
        (key,),
    ).fetchone()
    return str(row["value"]) if row is not None else None


def set_state(
    connection: sqlite3.Connection,
    *,
    key: str,
    value: str,
    updated_at: str,
) -> None:
    connection.execute(
        """
        insert into state (key, value, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set
          value = excluded.value,
          updated_at = excluded.updated_at
        """,
        (key, value, updated_at),
    )


def get_thread(
    connection: sqlite3.Connection,
    gmail_thread_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        select gmail_thread_id, slack_channel_id, slack_thread_ts, subject
        from threads
        where gmail_thread_id = ?
        """,
        (gmail_thread_id,),
    ).fetchone()


def save_thread(
    connection: sqlite3.Connection,
    *,
    gmail_thread_id: str,
    slack_channel_id: str,
    slack_thread_ts: str,
    subject: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        insert into threads (
          gmail_thread_id, slack_channel_id, slack_thread_ts, subject, created_at
        )
        values (?, ?, ?, ?, ?)
        on conflict(gmail_thread_id) do update set
          slack_channel_id = excluded.slack_channel_id,
          slack_thread_ts = excluded.slack_thread_ts,
          subject = excluded.subject
        """,
        (gmail_thread_id, slack_channel_id, slack_thread_ts, subject, created_at),
    )


def save_message(
    connection: sqlite3.Connection,
    *,
    message_id: str,
    gmail_uid: str,
    gmail_thread_id: str,
    slack_channel_id: str,
    slack_ts: str,
    direction: str,
    subject: str,
    processed_at: str,
) -> None:
    connection.execute(
        """
        insert into messages (
          message_id, gmail_uid, gmail_thread_id, slack_channel_id,
          slack_ts, direction, subject, processed_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(message_id) do update set
          gmail_uid = excluded.gmail_uid,
          gmail_thread_id = excluded.gmail_thread_id,
          slack_channel_id = excluded.slack_channel_id,
          slack_ts = excluded.slack_ts,
          direction = excluded.direction,
          subject = excluded.subject,
          processed_at = excluded.processed_at
        """,
        (
            message_id,
            gmail_uid,
            gmail_thread_id,
            slack_channel_id,
            slack_ts,
            direction,
            subject,
            processed_at,
        ),
    )
