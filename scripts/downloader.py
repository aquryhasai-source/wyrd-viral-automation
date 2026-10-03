"""
Downloads a candidate's source video via yt-dlp. Works for YouTube and most
sites Reddit links point to (v.redd.it, gfycat, imgur, direct-linked mp4s,
etc.) yt-dlp does not reliably support Instagram/TikTok -- those remain
outside automated retrieval, by design, per the earlier scoping discussion.
"""
import os
import subprocess
import uuid


def download(url: str, out_dir: str = "/tmp/tmp_media") -> str | None:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{uuid.uuid4()}.mp4")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "--max-filesize", "200M",
        "-o", out_path,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"yt-dlp failed for {url}: {result.stderr}")
        return None

    return out_path if os.path.exists(out_path) else None
