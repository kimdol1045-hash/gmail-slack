from __future__ import annotations

import argparse
import logging
from pathlib import Path
import time

from app.config import load_config
from app.mirror import MirrorService


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror Gmail threads into Slack threads.")
    parser.add_argument("--once", action="store_true", help="Run one polling pass and exit.")
    parser.add_argument("--limit", type=int, default=None, help="Number of recent messages to scan.")
    parser.add_argument("--init-db", action="store_true", help="Initialize SQLite and exit.")
    parser.add_argument(
        "--bootstrap-existing",
        action="store_true",
        help="Mark currently fetched Gmail messages as processed without Slack posts.",
    )
    parser.add_argument(
        "--seed-recent-threads",
        action="store_true",
        help="Mirror recent Gmail threads into Slack, then set the Gmail history baseline.",
    )
    args = parser.parse_args()

    needs_runtime = not args.init_db
    config = load_config(
        require_gmail=needs_runtime,
        require_slack=needs_runtime and not args.bootstrap_existing,
    )
    configure_logging(config.log_file, config.log_level)
    service = MirrorService(config)

    if args.init_db:
        service.init_db()
        print(f"Initialized database at {config.database_path}")
        return

    if args.bootstrap_existing:
        marked_count = service.bootstrap_existing(limit=args.limit)
        print(f"Bootstrapped {marked_count} existing Gmail message(s) without Slack posts.")
        return

    if args.seed_recent_threads:
        seed_limit = args.limit if args.limit is not None else 30
        posted_count = service.seed_recent_threads(limit=seed_limit)
        print(f"Seeded recent Gmail threads with {posted_count} Gmail message(s) mirrored to Slack.")
        return

    if args.once:
        posted_count = service.run_once(limit=args.limit)
        print(f"Posted {posted_count} new Gmail message(s) to Slack.")
        return

    while True:
        try:
            posted_count = service.run_once(limit=args.limit)
            logging.info("Posted %s new Gmail message(s) to Slack.", posted_count)
        except KeyboardInterrupt:
            raise
        except Exception:
            logging.exception("Polling pass failed")
        time.sleep(config.poll_interval_seconds)


def configure_logging(log_file: str, log_level: str) -> None:
    level = getattr(logging, log_level, logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )


if __name__ == "__main__":
    main()
