"""
Sends the approval-gate message: video preview + details + inline
Approve/Reject buttons. The button taps are handled by the Cloudflare Worker
(see cloudflare-worker/telegram-webhook.js), which dispatches approve_post /
reject_post to GitHub Actions.

Telegram bots can upload at most 50 MB; a bigger preview is sent as a link instead.

Requires env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import json
import os

import requests

API_BASE = "https://api.telegram.org/bot{token}"
MAX_UPLOAD_BYTES = 49 * 1024 * 1024
CAPTION_LIMIT = 1024


def _keyboard(post_db_id: str) -> str:
    return json.dumps({
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{post_db_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{post_db_id}"},
        ]]
    })


def send_approval_request(video_path: str, caption: str, post_db_id: str, fallback_url: str = "") -> str | None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base = API_BASE.format(token=token)
    caption = caption[: CAPTION_LIMIT - 1]

    if os.path.getsize(video_path) <= MAX_UPLOAD_BYTES:
        with open(video_path, "rb") as video_file:
            response = requests.post(
                f"{base}/sendVideo",
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                    "reply_markup": _keyboard(post_db_id),
                    "supports_streaming": "true",
                    "width": 1080,
                    "height": 1920,
                },
                files={"video": video_file},
                timeout=300,
            )
    else:
        text = f"{caption}\n\n⚠️ Preview is over Telegram's 50 MB limit. Watch it here:\n{fallback_url}"
        response = requests.post(
            f"{base}/sendMessage",
            data={"chat_id": chat_id, "text": text[:4000], "reply_markup": _keyboard(post_db_id)},
            timeout=30,
        )

    if not response.ok:
        print(f"Telegram send failed: {response.text}")
        return None
    return str(response.json()["result"]["message_id"])
