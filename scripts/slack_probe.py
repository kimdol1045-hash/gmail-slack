from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.slack_client import SlackPoster


def main() -> None:
    config = load_config(require_slack=True)
    slack = SlackPoster(
        bot_token=config.slack_bot_token,
        channel_id=config.slack_channel_id,
        user_id=config.slack_user_id,
    )

    parent_ts = slack.post_message("Gmail Slack mirror probe: parent message")
    reply_ts = slack.post_message(
        "Gmail Slack mirror probe: thread reply",
        thread_ts=parent_ts,
    )

    print(f"parent_ts={parent_ts}")
    print(f"reply_ts={reply_ts}")


if __name__ == "__main__":
    main()
