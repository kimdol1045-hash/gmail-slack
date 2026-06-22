from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.gmail_api_client import GmailApiClient, OAuthPaths, authorize_oauth
from app.mail_parser import parse_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Gmail API OAuth access.")
    parser.add_argument("--limit", type=int, default=10, help="Recent message count to fetch.")
    parser.add_argument(
        "--authorize-only",
        action="store_true",
        help="Run OAuth flow, save token, and exit.",
    )
    args = parser.parse_args()

    config = load_config()
    if not config.google_client_secret_file:
        raise RuntimeError("Missing required environment value: GOOGLE_CLIENT_SECRET_FILE")
    paths = OAuthPaths(
        client_secret_file=config.google_client_secret_file,
        token_file=config.google_token_file,
    )

    if args.authorize_only:
        authorize_oauth(paths)
        print(f"Saved Google OAuth token to {config.google_token_file}")
        return

    with GmailApiClient(
        client_secret_file=config.google_client_secret_file,
        token_file=config.google_token_file,
        query=config.gmail_query,
    ) as gmail:
        messages = gmail.fetch_recent(args.limit)
        my_email = config.gmail_email or gmail.profile_email()

    rows = []
    for raw_message in messages:
        parsed = parse_email(
            uid=raw_message.uid,
            gmail_thread_id=raw_message.gmail_thread_id,
            raw_bytes=raw_message.raw_bytes,
            my_email=my_email,
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
