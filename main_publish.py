"""
Entry point for the "publish" workflow (.github/workflows/publish.yml),
triggered by a repository_dispatch event from the Cloudflare Worker when
you tap Approve/Reject in Telegram.

Expects two env vars set by the workflow from the dispatch payload:
  POST_ID      -- the Supabase posts.id the Telegram callback referenced
  DECISION     -- "approve" or "reject"
"""
import os

from scripts.db import update_status, get_client
from scripts.storage import download_pending_clip, delete_pending_clip
from scripts.publish_youtube import upload_short
from scripts.publish_meta import publish_to_facebook, publish_to_instagram


def run():
    post_id = os.environ["POST_ID"]
    decision = os.environ["DECISION"]

    client = get_client()
    post = client.table("wyrd_viral_posts").select("*").eq("id", post_id).execute().data[0]

    if decision == "reject":
        update_status(post_id, "rejected")
        delete_pending_clip(post["storage_path"])
        print(f"Post {post_id} rejected and cleaned up.")
        return

    local_path = f"/tmp/{post['storage_path']}"
    download_pending_clip(post["storage_path"], local_path)

    platform_post_ids = {}

    youtube_id = upload_short(local_path, post["title"], post["caption"])
    if youtube_id:
        platform_post_ids["youtube"] = youtube_id

    # Facebook/Instagram need a public URL, not a local file -- reuse the
    # Supabase Storage public URL directly rather than re-uploading.
    public_url = get_client().storage.from_("wyrd-viral-pending-clips").get_public_url(post["storage_path"])

    fb_id = publish_to_facebook(public_url, post["caption"])
    if fb_id:
        platform_post_ids["facebook"] = fb_id

    ig_id = publish_to_instagram(public_url, post["caption"])
    if ig_id:
        platform_post_ids["instagram"] = ig_id

    update_status(post_id, "published", platform_post_ids)
    delete_pending_clip(post["storage_path"])
    print(f"Post {post_id} published: {platform_post_ids}")


if __name__ == "__main__":
    run()
