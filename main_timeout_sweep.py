"""
Entry point for the scheduled "timeout sweep" workflow. Finds posts still
"pending" past config.APPROVAL_TIMEOUT_HOURS and resolves them according to
config.APPROVAL_DEFAULT_ON_TIMEOUT ("reject" by default -- see spec
rationale for why this starts conservative).
"""
import os
from datetime import datetime, timezone

from scripts.db import get_stale_pending, update_status
from scripts.storage import delete_pending_clip
from config import APPROVAL_TIMEOUT_HOURS, APPROVAL_DEFAULT_ON_TIMEOUT


def run():
    pending = get_stale_pending(APPROVAL_TIMEOUT_HOURS)
    now = datetime.now(timezone.utc)

    for post in pending:
        created_at = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created_at).total_seconds() / 3600

        if age_hours < APPROVAL_TIMEOUT_HOURS:
            continue

        if APPROVAL_DEFAULT_ON_TIMEOUT == "reject":
            update_status(post["id"], "rejected")
            delete_pending_clip(post["storage_path"])
            print(f"Timed out, auto-rejected: {post['id']}")
        else:
            # Re-dispatch into the same publish path approvals use, so there
            # is only one place that actually posts to the platforms.
            os.environ["POST_ID"] = post["id"]
            os.environ["DECISION"] = "approve"
            from main_publish import run as publish_run
            publish_run()


if __name__ == "__main__":
    run()
