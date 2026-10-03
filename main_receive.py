"""
Entry point for the "receive_video" workflow (.github/workflows/receive.yml).
Triggered by the Cloudflare Worker when you send a video to the Telegram bot.

Env vars set by the workflow from dispatch payload:
  FILE_ID   -- Telegram file_id of the video you sent
  CAPTION   -- caption you typed (or empty -- Groq auto-generates one)
"""
import os
import uuid

from scripts.telegram_video_download import download_video
from scripts.caption_gen import generate_caption
from scripts.video_editor import edit_video
from scripts.publish_youtube import upload_short
from scripts.publish_meta import publish_to_facebook, publish_to_instagram
from scripts.storage import upload_pending_clip, delete_pending_clip
from scripts.db import insert_pending, update_status
from scripts.telegram_reminder import send_message


def run():
    file_id = os.environ["FILE_ID"]
    caption = os.environ.get("CAPTION", "").strip()

    # Download from Telegram (no bot-blocking -- it's our own bot's server)
    os.makedirs("/tmp/tmp_media", exist_ok=True)
    raw_path = download_video(file_id)
    if not raw_path:
        send_message("❌ Couldn't download your video. Please try sending it again.")
        return

    # Generate caption if you didn't type one
    if not caption:
        caption = generate_caption("trending viral video clip")

    # Edit: crop to vertical, watermark, caption overlay
    edited_path = f"/tmp/tmp_media/{uuid.uuid4()}_edited.mp4"
    if not edit_video(raw_path, edited_path, caption):
        send_message("❌ Video processing failed. Try a shorter or smaller clip.")
        return

    # Log to Supabase
    source_id = f"tg_{uuid.uuid4()}"
    insert_result = insert_pending(
        source_id=source_id,
        source_platform="telegram",
        title=caption,
        caption=caption,
        storage_path="",
        telegram_message_id="",
    )
    post_id = insert_result.data[0]["id"]

    # Publish to YouTube Shorts
    platform_post_ids = {}
    youtube_id = upload_short(edited_path, caption, caption)
    if youtube_id:
        platform_post_ids["youtube"] = youtube_id
        print(f"YouTube: {youtube_id}")

    # For Facebook + Instagram upload to Supabase Storage first (needs public URL)
    storage_filename = f"{uuid.uuid4()}.mp4"
    try:
        public_url = upload_pending_clip(edited_path, storage_filename)

        fb_id = publish_to_facebook(public_url, caption)
        if fb_id:
            platform_post_ids["facebook"] = fb_id
            print(f"Facebook: {fb_id}")

        ig_id = publish_to_instagram(public_url, caption)
        if ig_id:
            platform_post_ids["instagram"] = ig_id
            print(f"Instagram: {ig_id}")
    except Exception as e:
        print(f"Meta publish error (may need app review): {e}")
    finally:
        try:
            delete_pending_clip(storage_filename)
        except Exception:
            pass

    update_status(post_id, "published", platform_post_ids)

    platforms = ", ".join(platform_post_ids.keys()) or "none yet"
    send_message(
        f"✅ <b>Posted!</b>\n"
        f"📱 Platforms: {platforms}\n"
        f"📝 Caption: {caption}"
    )


if __name__ == "__main__":
    run()
