"""
Sends the approval-gate message: video preview + caption + inline
Approve/Reject buttons. The callback itself is handled by the Cloudflare
Worker (see cloudflare-worker/telegram-webhook.js), not here -- this script
only sends the message and returns its message_id for tracking.

Requires env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os
import requests

API_BASE = "https://api.telegram.org/bot{token}"


def send_approval_request(video_path: str, caption: str, post_db_id: str) -> str | None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"{API_BASE.format(token=token)}/sendVideo"

    # Encode the DB row id into the callback_data so the worker knows which
    # row to update when the button is tapped.
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{post_db_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{post_db_id}"},
        ]]
    }

    with open(video_path, "rb") as video_file:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": caption,
                "reply_markup": str(keyboard).replace("'", '"'),
            },
            files={"video": video_file},
            timeout=60,
        )

    if not response.ok:
        print(f"Telegram send failed: {response.text}")
        return None

    return str(response.json()["result"]["message_id"])
