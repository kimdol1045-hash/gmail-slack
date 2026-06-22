from __future__ import annotations


class SlackPoster:
    def __init__(
        self,
        *,
        bot_token: str,
        channel_id: str = "",
        user_id: str = "",
    ) -> None:
        try:
            from slack_sdk import WebClient
        except ImportError as exc:
            raise RuntimeError(
                "slack_sdk is not installed. Run: python3 -m pip install -r requirements.txt"
            ) from exc

        self._client = WebClient(token=bot_token)
        self.channel_id = channel_id or self._open_dm(user_id)

    def post_message(self, text: str, *, thread_ts: str | None = None) -> str:
        response = self._client.chat_postMessage(
            channel=self.channel_id,
            text=_fit_slack_text(text),
            thread_ts=thread_ts,
            unfurl_links=False,
            unfurl_media=False,
        )
        if not response.get("ok"):
            raise RuntimeError(f"Slack postMessage failed: {response}")
        return str(response["ts"])

    def _open_dm(self, user_id: str) -> str:
        if not user_id:
            raise RuntimeError("Set SLACK_CHANNEL_ID or SLACK_USER_ID")
        response = self._client.conversations_open(users=user_id)
        if not response.get("ok"):
            raise RuntimeError(f"Slack conversations.open failed: {response}")
        channel = response.get("channel") or {}
        channel_id = channel.get("id")
        if not channel_id:
            raise RuntimeError(f"Slack conversations.open returned no channel id: {response}")
        return str(channel_id)


def _fit_slack_text(text: str) -> str:
    max_length = 35_000
    if len(text) <= max_length:
        return text
    return text[: max_length - 80].rstrip() + "\n\n...(truncated for Slack message limit)"
