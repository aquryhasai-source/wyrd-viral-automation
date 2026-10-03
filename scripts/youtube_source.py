"""
Polls MrBeast's channel for new uploads since the last check.
Requires env var: YOUTUBE_API_KEY (a simple API key is enough for read-only
search -- the OAuth credentials in publish_youtube.py are separate and only
needed for uploading).
"""
import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from config import MRBEAST_CHANNEL_ID


def fetch_candidates(lookback_hours=12):
    youtube = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])
    published_after = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    response = youtube.search().list(
        part="snippet",
        channelId=MRBEAST_CHANNEL_ID,
        order="date",
        publishedAfter=published_after,
        maxResults=5,
        type="video",
    ).execute()

    candidates = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        candidates.append({
            "source": "youtube",
            "id": video_id,
            "title": item["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "score": None,  # no comparable score field
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
            "flair": "mrbeast",
            "domain": "youtube.com",
        })
    return candidates


if __name__ == "__main__":
    for c in fetch_candidates():
        print(c["title"], c["url"])
