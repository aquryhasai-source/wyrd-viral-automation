"""
Uploads the final edited video as a YouTube Short.
Requires env vars: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
These come from a one-time OAuth consent flow for the WYRD VIRAL channel --
see README "One-time setup" for how to generate the refresh token.
"""
import os
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


def upload_short(video_path: str, title: str, description: str) -> str | None:
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{description}\n\n#shorts",
            "categoryId": "24",  # Entertainment
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
