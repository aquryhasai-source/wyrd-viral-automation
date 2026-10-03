"""
Entry point for the scheduled "discover" workflow (.github/workflows/discover.yml).

Pipeline: source discovery -> dedup -> filter -> download -> caption ->
edit -> upload to pending storage -> send Telegram approval request -> log.

Processes at most ONE candidate per run, to keep each run simple and keep
the approval queue from backing up. Raise this later once comfortable.
"""
import os
import uuid

from scripts.reddit_source import fetch_candidates as fetch_reddit
from scripts.youtube_source import fetch_candidates as fetch_youtube
from scripts.content_filter import filter_candidates
from scripts.downloader import download
from scripts.caption_gen import generate_caption
from scripts.video_editor import edit_video
from scripts.storage import upload_pending_clip
from scripts.telegram_notify import send_approval_request
from scripts.db import already_used, insert_pending


def run():
    candidates = fetch_reddit() + fetch_youtube()
    candidates = filter_candidates(candidates)
    candidates.sort(key=lambda c: c.get("score") or 0, reverse=True)

    for candidate in candidates:
        if already_used(candidate["id"]):
            continue

        print(f"Selected candidate: {candidate['title']} ({candidate['url']})")

        raw_path = download(candidate["url"])
        if not raw_path:
            print("Download failed, trying next candidate")
            continue

        caption = generate_caption(candidate["title"])
        edited_path = f"/tmp/tmp_media/{uuid.uuid4()}_edited.mp4"

        if not edit_video(raw_path, edited_path, caption):
            print("Edit failed, trying next candidate")
            continue

        storage_filename = f"{uuid.uuid4()}.mp4"
        public_url = upload_pending_clip(edited_path, storage_filename)

        # Insert the DB row first (without telegram_message_id) so we have
        # a stable id to embed in the Telegram callback_data.
        insert_result = insert_pending(
            source_id=candidate["id"],
            source_platform=candidate["source"],
            title=candidate["title"],
            caption=caption,
            storage_path=storage_filename,
            telegram_message_id="",
        )
        post_id = insert_result.data[0]["id"]

        message_id = send_approval_request(edited_path, caption, post_id)
        if message_id:
            from scripts.db import get_client
            get_client().table("wyrd_viral_posts").update({"telegram_message_id": message_id}).eq("id", post_id).execute()

        print(f"Sent for approval: post_id={post_id}, telegram_message_id={message_id}")
        return  # one candidate per run

    print("No eligible candidates found this run.")


if __name__ == "__main__":
    run()
