"""
Entry point for the "publish" workflow (.github/workflows/publish.yml),
triggered by a repository_dispatch event from the Cloudflare Worker when
you tap Approve/Reject on a preview in Telegram.

Env vars set by the workflow from the dispatch payload:
  POST_ID      -- the Supabase wyrd_viral_posts.id the Telegram button referenced
  DECISION     -- "approve" or "reject"

Title / description / tags come from the JSON file stored next to the clip
(see scripts/storage.py); posts from the old discover flow have none and fall
back to the database columns.
"""
import html
import os

import config as cfg

from scripts.db import update_status, get_client
from scripts.storage import download_pending_clip, delete_pending_clip, download_pending_meta
from scripts.publish_youtube import upload_short
from scripts.telegram_reminder import send_message
from scripts.telegram_notify import send_approval_request


def run():
    post_id = os.environ["POST_ID"]
    decision = os.environ["DECISION"]

    client = get_client()
    rows = client.table("wyrd_viral_posts").select("*").eq("id", post_id).execute().data
    if not rows:
        send_message("⚠️ That preview no longer exists (it may have expired).")
        return
    post = rows[0]

    if post["status"] != "pending":
        print(f"Post {post_id} is already {post['status']}; ignoring {decision}.")
        send_message(f"ℹ️ That video was already {post['status']}.")
        return

    if decision == "reject":
        update_status(post_id, "rejected")
        delete_pending_clip(post["storage_path"])
        print(f"Post {post_id} rejected and cleaned up.")
        return

    meta = download_pending_meta(post["storage_path"])
    title = meta.get("title") or post["title"]
    description = meta.get("description") or post["caption"] or title
    tags = meta.get("tags", "")

    local_path = f"/tmp/{post['storage_path']}"
    download_pending_clip(post["storage_path"], local_path)

    platform_post_ids = {}
    youtube_id = upload_short(local_path, title, description, tags)
    if youtube_id:
        platform_post_ids["youtube"] = youtube_id
    else:
        # Keep the clip and offer the buttons again so you can retry
        send_message("❌ YouTube upload failed. The preview is kept; tap Approve again to retry.")
        send_approval_request(local_path, f"RETRY — {title}", post_id)
        return

    if cfg.PUBLISH_META:
        # Facebook/Instagram need a public URL, not a local file
        from scripts.publish_meta import publish_to_facebook, publish_to_instagram
        public_url = client.storage.from_("wyrd-viral-pending-clips").get_public_url(post["storage_path"])
        fb_id = publish_to_facebook(public_url, description)
        if fb_id:
            platform_post_ids["facebook"] = fb_id
        ig_id = publish_to_instagram(public_url, description)
        if ig_id:
            platform_post_ids["instagram"] = ig_id

    update_status(post_id, "published", platform_post_ids)
    delete_pending_clip(post["storage_path"])
    print(f"Post {post_id} published: {platform_post_ids}")

    send_message(
        f"✅ <b>Posted to YouTube!</b>\n"
        f"📝 {html.escape(title)}\n"
        f"https://youtube.com/shorts/{youtube_id}"
    )


if __name__ == "__main__":
    run()
