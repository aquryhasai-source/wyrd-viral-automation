"""
YouTube source discovery:
1. Trending videos globally (chart=mostPopular) -- constant stream of viral content
2. New uploads from MrBeast's channel (lookback 7 days)

Requires env var: YOUTUBE_API_KEY
Reddit was removed as a source: datacenter IPs (GitHub Actions/Azure) are
blocked by Reddit with a 403, making it unusable in scheduled workflows.
"""
import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from config import MRBEAST_CHANNEL_ID

REGION_CODE = "IN"  # India -- change to "US" for global trending


def get_youtube():
    return build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])


def fetch_trending(max_results=20):
    """Pull YouTube's Most Popular chart -- always has viral candidates."""
    youtube = get_youtube()
    response = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=REGION_CODE,
        maxResults=max_results,
        videoCategoryId="0",
    ).execute()

    candidates = []
    for item in response.get("items", []):
        video_id = item["id"]
        candidates.append({
            "source": "youtube_trending",
            "id": f"yt_trend_{video_id}",
            "title": item["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "score": 9999,
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
            "flair": "trending",
            "domain": "youtube.com",
        })
    return candidates


def fetch_mrbeast(lookback_days=7):
    """Poll MrBeast's channel for recent uploads."""
    youtube = get_youtube()
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=lookback_days)
    ).isoformat()

    response = youtube.search().list(
        part="snippet",
        channelId=MRBEAST_CHANNEL_ID,
        order="date",
        publishedAfter=published_after,
        maxResults=10,
        type="video",
    ).execute()

    candidates = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        candidates.append({
            "source": "youtube_mrbeast",
            "id": f"yt_mb_{video_id}",
            "title": item["snippet"]["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "score": 9000,
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
            "flair": "mrbeast",
            "domain": "youtube.com",
        })
    return candidates


def fetch_candidates():
    """Combined: trending + MrBeast recent uploads."""
    candidates = []
    try:
        t = fetch_trending()
        candidates += t
        print(f"YouTube trending: {len(t)} candidates")
    except Exception as e:
        print(f"YouTube trending fetch failed: {e}")
    try:
        mb = fetch_mrbeast()
        candidates += mb
        print(f"MrBeast recent: {len(mb)} candidates")
    except Exception as e:
        print(f"MrBeast fetch failed: {e}")
    return candidates


if __name__ == "__main__":
    for c in fetch_candidates():
        print(c["score"], c["title"], c["url"])
