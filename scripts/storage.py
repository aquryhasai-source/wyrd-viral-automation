"""
Supabase Storage helper -- holds the edited video between the discover
workflow run (which renders it) and the publish workflow run (which needs
it again after approval), since GitHub Actions runners don't persist files
between separate workflow runs.

One-time setup: create a public bucket called "wyrd-viral-pending-clips" in the
Supabase dashboard before first use.

Requires env vars: SUPABASE_URL, SUPABASE_KEY
"""
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


def delete_pending_clip(storage_filename: str):
    client = get_client()
    client.storage.from_(BUCKET).remove([storage_filename])
