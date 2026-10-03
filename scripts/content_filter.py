"""
Auto-reject pass (Step 4 of the pipeline). Keyword/domain heuristics only --
this is a blunt first filter, not a legal judgment. Tune BLOCKLIST_* in
config.py as real-world claim patterns emerge.
"""
from config import BLOCKLIST_KEYWORDS, BLOCKLIST_DOMAINS


def is_allowed(candidate: dict) -> bool:
    title = candidate.get("title", "").lower()
    domain = candidate.get("domain", "").lower()

    for keyword in BLOCKLIST_KEYWORDS:
        if keyword in title:
            return False

    for blocked_domain in BLOCKLIST_DOMAINS:
        if blocked_domain in domain:
            return False

    return True


def filter_candidates(candidates: list) -> list:
    return [c for c in candidates if is_allowed(c)]
