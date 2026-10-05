"""
Supabase Storage helper -- holds the edited video between the discover
workflow run (which renders it) and the publish workflow run (which needs
it again after approval), since GitHub Actions runners don't persist files
between separate workflow runs.

One-time setup: create a public bucket called "wyrd-viral-pending-clips" in the
Supabase dashboard before first use.

Requires env vars: SUPABASE_URL, SUPABASE_KEY
"""
import json
import os
from scripts.db import get_client

BUCKET = "wyrd-viral-pending-clips"


def upload_pending_clip(local_path: str, storage_filename: str) -> str:
    client = get_client()
    with open(local_path, "rb") as f:
        client.storage.from_(BUCKET).upload(storage_filename, f, {"content-type": "video/mp4"})
    return client.storage.from_(BUCKET).get_public_url(storage_filename)


def download_pending_clip(storage_filename: str, local_path: str) -> str:
    client = get_client()
    data = client.storage.from_(BUCKET).download(storage_filename)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path


def _meta_name(storage_filename: str) -> str:
    return os.path.splitext(storage_filename)[0] + ".json"


def upload_pending_meta(storage_filename: str, meta: dict) -> None:
    """Title/description/tags travel with the clip as a small JSON file next to it."""
    client = get_client()
    client.storage.from_(BUCKET).upload(
        _meta_name(storage_filename),
        json.dumps(meta).encode("utf-8"),
        {"content-type": "application/json"},
    )


def download_pending_meta(storage_filename: str) -> dict:
    """Returns {} when there is no metadata file (e.g. posts from the old discover flow)."""
    try:
        data = get_client().storage.from_(BUCKET).download(_meta_name(storage_filename))
        return json.loads(data.decode("utf-8"))
    except Exception:
        return {}


def delete_pending_clip(storage_filename: str):
    client = get_client()
    client.storage.from_(BUCKET).remove([storage_filename, _meta_name(storage_filename)])
