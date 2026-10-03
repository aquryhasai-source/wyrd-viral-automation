"""
Supabase client -- dedup check, posting a pending record, and reading/updating
status across the two workflow runs (discover -> approve/publish).

Expected table schema (create this once in the Supabase SQL editor):

create table wyrd_viral_posts (
    id uuid primary key default gen_random_uuid(),
    source_id text unique not null,
    source_platform text not null,
    title text,
    caption text,
    storage_path text,
    telegram_message_id text,
    status text default 'pending',  -- pending | approved | rejected | published
    platform_post_ids jsonb default '{}',
    created_at timestamptz default now()
);

Requires env vars: SUPABASE_URL, SUPABASE_KEY
"""
import os
from supabase import create_client


def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def already_used(source_id: str) -> bool:
    client = get_client()
    result = client.table("wyrd_viral_posts").select("id").eq("source_id", source_id).execute()
    return len(result.data) > 0


def insert_pending(source_id, source_platform, title, caption, storage_path, telegram_message_id):
    client = get_client()
    return client.table("wyrd_viral_posts").insert({
        "source_id": source_id,
        "source_platform": source_platform,
        "title": title,
        "caption": caption,
        "storage_path": storage_path,
        "telegram_message_id": telegram_message_id,
        "status": "pending",
    }).execute()


def get_by_telegram_message_id(telegram_message_id: str):
    client = get_client()
    result = client.table("wyrd_viral_posts").select("*").eq("telegram_message_id", telegram_message_id).execute()
    return result.data[0] if result.data else None


def update_status(post_id: str, status: str, platform_post_ids: dict = None):
    client = get_client()
    payload = {"status": status}
    if platform_post_ids is not None:
        payload["platform_post_ids"] = platform_post_ids
    return client.table("wyrd_viral_posts").update(payload).eq("id", post_id).execute()


def get_stale_pending(older_than_hours: int):
    """Used by main_publish.py's timeout sweep -- see config.APPROVAL_TIMEOUT_HOURS."""
    client = get_client()
    result = client.table("wyrd_viral_posts").select("*").eq("status", "pending").execute()
    return result.data
