"""
Pulls candidate posts from the configured subreddits via Reddit's public
.json endpoints -- no registered Reddit app or OAuth credentials needed.
(Reddit has recently made new "script" app creation unreliable/gated for
many accounts, so this sidesteps that entirely.)

A descriptive User-Agent is required or Reddit will rate-limit/block the
request -- no other setup needed.
"""
import requests
from config import SUBREDDITS, REDDIT_POST_LIMIT_PER_SUB, REDDIT_MIN_SCORE

HEADERS = {"User-Agent": "wyrd-viral-automation/1.0 (personal use script)"}


def fetch_candidates():
    """
    Returns a list of dicts: {source: "reddit", id, title, url, score, permalink}
    """
    candidates = []

    for sub_name in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub_name}/rising.json?limit={REDDIT_POST_LIMIT_PER_SUB}"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if not response.ok:
            print(f"Reddit fetch failed for r/{sub_name}: {response.status_code}")
            continue

        posts = response.json().get("data", {}).get("children", [])

        for post in posts:
            data = post["data"]
            if data.get("score", 0) < REDDIT_MIN_SCORE:
                continue
            if data.get("is_self"):
                continue  # text post, no media

            candidates.append({
                "source": "reddit",
                "id": data["id"],
                "title": data["title"],
                "url": data["url"],
                "score": data["score"],
                "permalink": f"https://reddit.com{data['permalink']}",
                "flair": data.get("link_flair_text") or "",
                "domain": data.get("domain", ""),
            })

    return candidates


if __name__ == "__main__":
    for c in fetch_candidates():
        print(c["score"], c["title"], c["url"])
