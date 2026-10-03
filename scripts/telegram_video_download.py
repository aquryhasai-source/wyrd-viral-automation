"""
Downloads a video file from Telegram's servers using the file_id.
Works for videos sent directly as video messages or as document files.
Telegram Bot API getFile supports files up to 20MB -- enough for short clips.
Requires env var: TELEGRAM_BOT_TOKEN
"""
import os
import uuid
import requests

def download_video(file_id: str, out_dir: str = "/tmp/tmp_media") -> str | None:
    os.makedirs(out_dir, exist_ok=True)
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    # Step 1: get the file path on Telegram's servers
    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getFile",
        params={"file_id": file_id},
        timeout=15,
    )
    if not resp.ok:
        print(f"getFile failed: {resp.text}")
        return None

    file_path = resp.json()["result"]["file_path"]
    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

    # Step 2: stream download to disk
    out_path = os.path.join(out_dir, f"{uuid.uuid4()}.mp4")
    r = requests.get(download_url, stream=True, timeout=120)
    if not r.ok:
        print(f"Video download failed: {r.text}")
        return None

    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Downloaded to {out_path}")
    return out_path
