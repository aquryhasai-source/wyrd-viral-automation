"""
Publishes to a Facebook Page and an Instagram Business account via the Meta
Graph API. Requires app review approval for the relevant permissions before
this will work in production (see README).

Requires env vars: META_PAGE_ID, META_PAGE_ACCESS_TOKEN,
META_IG_BUSINESS_ACCOUNT_ID

Note: both endpoints need a *publicly reachable URL* for the video, not a
local file -- this implementation assumes the edited video has already been
uploaded to Supabase Storage and passes that public URL in.
"""
import os
import time
import requests

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def publish_to_facebook(video_public_url: str, caption: str) -> str | None:
    page_id = os.environ["META_PAGE_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]

    response = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/videos",
        data={
            "file_url": video_public_url,
            "description": caption,
            "access_token": token,
        },
        timeout=120,
    )
    if not response.ok:
        print(f"Facebook publish failed: {response.text}")
        return None
    return response.json().get("id")


def publish_to_instagram(video_public_url: str, caption: str) -> str | None:
    ig_account_id = os.environ["META_IG_BUSINESS_ACCOUNT_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]

    # Step 1: create a media container
    container_response = requests.post(
        f"{GRAPH_API_BASE}/{ig_account_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_public_url,
            "caption": caption,
            "access_token": token,
        },
        timeout=120,
    )
    if not container_response.ok:
        print(f"Instagram container creation failed: {container_response.text}")
        return None
    container_id = container_response.json()["id"]

    # Step 2: poll until the container finishes processing
    for _ in range(20):
        status_response = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        status = status_response.json().get("status_code")
        if status == "FINISHED":
            break
        time.sleep(15)
    else:
        print("Instagram container never finished processing")
        return None

    # Step 3: publish the container
    publish_response = requests.post(
        f"{GRAPH_API_BASE}/{ig_account_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    if not publish_response.ok:
        print(f"Instagram publish failed: {publish_response.text}")
        return None
    return publish_response.json().get("id")
