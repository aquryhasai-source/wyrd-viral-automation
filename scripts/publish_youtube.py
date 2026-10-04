"""
Uploads the final edited video as a YouTube Short.
Requires env vars: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
These come from a one-time OAuth consent flow for the WYRD VIRAL channel --
see README "One-time setup" for how to generate the refresh token.
"""
import os
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_authenticated_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


def clean_tags(raw) -> list[str]:
    """Accepts "a, b, #c" / newline-separated text or a list; returns YouTube-safe tags
    (deduped, no '#', total length kept under YouTube's 500-char limit)."""
    if isinstance(raw, str):
        parts = re.split(r"[,\n]+|\s#", raw)
    else:
        parts = list(raw or [])
    tags, seen, total = [], set(), 0
    for p in parts:
        t = p.strip().lstrip("#").strip()[:100]
        if not t or t.lower() in seen:
            continue
        if total + len(t) + 1 > 480:
            break
        seen.add(t.lower())
        tags.append(t)
        total += len(t) + 1
    return tags


def upload_short(video_path: str, title: str, description: str, tags=None) -> str | None:
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{description}\n\n#shorts",
            "categoryId": "24",  # Entertainment
            "tags": clean_tags(tags),
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response.get("id")
