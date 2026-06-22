from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.gmail_client import GmailClient
from app.mail_parser import parse_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Gmail IMAP access.")
    parser.add_argument("--limit", type=int, default=10, help="Recent message count to fetch.")
    parser.add_argument(
        "--list-mailboxes",
        action="store_true",
        help="List Gmail mailbox names and exit.",
    )
    args = parser.parse_args()

    config = load_config()
    missing = []
    if not config.gmail_email:
        missing.append("GMAIL_EMAIL")
    if not config.gmail_app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if missing:
        raise RuntimeError(f"Missing required environment values: {', '.join(missing)}")

    with GmailClient(
        email_address=config.gmail_email,
        app_password=config.gmail_app_password,
        mailbox=config.gmail_mailbox,
    ) as gmail:
        if args.list_mailboxes:
            print("\n".join(gmail.list_mailboxes()))
            return
        messages = gmail.fetch_recent(args.limit)

    rows = []
    for raw_message in messages:
        parsed = parse_email(
            uid=raw_message.uid,
            gmail_thread_id=raw_message.gmail_thread_id,
            raw_bytes=raw_message.raw_bytes,
            my_email=config.gmail_email,
        )
        rows.append(
            {
                "uid": parsed.uid,
                "gmail_thread_id": parsed.gmail_thread_id,
                "message_id": parsed.message_id,
                "direction": parsed.direction,
                "from": parsed.sender,
                "subject": parsed.subject,
                "date": parsed.date,
                "body_preview": parsed.body[:160],
            }
        )

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
