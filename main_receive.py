"""
Entry point for the "receive_video" workflow (.github/workflows/receive.yml).
Triggered by the Cloudflare Worker after you have sent a video AND answered
the title / description / tags / on-screen-title / subtitles questions.

This script does NOT post anything. It renders the video, stores it in
Supabase Storage, and sends you a preview in Telegram with Approve / Reject
buttons. Posting happens in main_publish.py after you tap Approve.

Env vars set by the workflow from the dispatch payload:
  FILE_ID      -- Telegram file_id of the video you sent
  TITLE        -- YouTube title you typed
  DESCRIPTION  -- YouTube description you typed
  TAGS         -- comma-separated tags / #hashtags you typed
  TITLE_ON     -- "1" = burn the title onto the video (first 3s, top), "0" = no on-screen title
  SUBS_ON      -- "1" = transcribe the narration and burn in subtitles, "0" = none
"""
import os
import uuid

import config as cfg

from scripts.telegram_video_download import download_video
from scripts.caption_gen import generate_caption
from scripts.video_editor import edit_video
from scripts.subtitles import transcribe_cues
from scripts.storage import upload_pending_clip, upload_pending_meta
from scripts.db import insert_pending
from scripts.telegram_reminder import send_message
from scripts.telegram_notify import send_approval_request


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip() in ("1", "true", "True", "on")


def run():
    file_id = os.environ["FILE_ID"]
    title = os.environ.get("TITLE", "").strip()
    description = os.environ.get("DESCRIPTION", "").strip()
    tags = os.environ.get("TAGS", "").strip()
    title_on = _flag("TITLE_ON", "1")
    subs_on = _flag("SUBS_ON", "0")

    # Download from Telegram
    os.makedirs("/tmp/tmp_media", exist_ok=True)
    raw_path = download_video(file_id)
    if not raw_path:
        send_message("❌ Couldn't download your video. Please try sending it again.")
        return

    if not title:
        title = generate_caption("trending viral video clip")
    if not description:
        description = title

    # Subtitles from the narration (optional)
    cues, subs_note = None, "off"
    if subs_on:
        cues, reason = transcribe_cues(raw_path)
        if cues is None:
            send_message(f"⚠️ Subtitles failed ({reason}); rendering without them.")
            subs_note = "failed"
        elif not cues:
            send_message(f"ℹ️ Subtitles skipped: {reason}.")
            subs_note = "none found"
            cues = None
        else:
            subs_note = f"on ({len(cues)} lines)"

    # Edit: vertical crop/fit, grade, watermark, title, subtitles, outro
    edited_path = f"/tmp/tmp_media/{uuid.uuid4()}_edited.mp4"
    if not edit_video(raw_path, edited_path, title if title_on else "", cues):
        send_message("❌ Video processing failed. Try a shorter or smaller clip.")
        return

    # Park the rendered clip + metadata in Supabase until you approve or reject
    storage_filename = f"{uuid.uuid4()}.mp4"
    try:
        public_url = upload_pending_clip(edited_path, storage_filename)
        upload_pending_meta(storage_filename, {
            "title": title,
            "description": description,
            "tags": tags,
            "title_on": title_on,
            "subtitles": subs_note,
        })
    except Exception as e:
        print(f"Storage upload failed: {e}")
        send_message("❌ Couldn't store the rendered video (it may be over Supabase's 50 MB file limit). Try a shorter clip.")
        return

    insert_result = insert_pending(
        source_id=f"tg_{uuid.uuid4()}",
        source_platform="telegram",
        title=title,
        caption=description,
        storage_path=storage_filename,
        telegram_message_id="",
    )
    post_id = insert_result.data[0]["id"]

    preview = (
        f"🎬 PREVIEW: approve to post on YouTube\n\n"
        f"Title: {title}\n"
        f"On-screen title: {'on' if title_on else 'off'} | Subtitles: {subs_note}\n"
        f"Tags: {tags or 'none'}\n\n"
        f"{description}"
    )
    if not send_approval_request(edited_path, preview, post_id, public_url):
        send_message("❌ Rendered the video but couldn't send the preview. Check the Actions log.")


if __name__ == "__main__":
    run()
