"""
Central, non-secret configuration. Tune these without touching pipeline logic.
Secrets (API keys/tokens) live in environment variables / GitHub Actions secrets,
never here.
"""

# --- Source discovery ---
SUBREDDITS = [
    "nextfuckinglevel",
    "oddlysatisfying",
    "Damnthatsinteresting",
    "AnimalsBeingBros",
    "sports",
]
REDDIT_POST_LIMIT_PER_SUB = 10  # candidates pulled per subreddit per run
REDDIT_MIN_SCORE = 500  # skip low-traction posts

MRBEAST_CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"  # verified current as of Oct 2026

# --- Content filter (Step 4: auto-reject) ---
# Keyword heuristics applied to post title/flair/domain. This is a blunt
# first pass, not a legal judgment -- tune based on what actually gets
# claimed once the pipeline is running.
BLOCKLIST_KEYWORDS = [
    "espn", "nba", "nfl", "fifa", "uefa", "premier league",  # official sports broadcasts
    "official trailer", "movie clip", "full movie", "netflix", "hbo", "disney",
    "official music video", "lyric video",
]
BLOCKLIST_DOMAINS = [
    "espn.com", "nba.com", "nfl.com",
]

# --- Editing ---
OUTPUT_RESOLUTION = (1080, 1920)  # vertical short format
WATERMARK_PATH = "assets/watermark.png"  # supply your own logo here
WATERMARK_POSITION = "bottom_right"
CAPTION_FONT_SIZE = 64

# --- Scheduling (informational -- actual schedule lives in the workflow YAML) ---
RUNS_PER_DAY = 2

# --- Approval gate ---
APPROVAL_TIMEOUT_HOURS = 6
APPROVAL_DEFAULT_ON_TIMEOUT = "reject"  # "reject" or "approve" -- start conservative
