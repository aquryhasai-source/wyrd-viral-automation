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

# --- Editing (ported from WyrdEngine_v1 config.yaml -- values tuned over ~2 months) ---
OUTPUT_RESOLUTION = (1080, 1920)  # vertical short format
FPS = 30

# Landscape/square clips: "blur" = fitted clip over a blurred, darkened fill of
# itself (nothing cropped); "crop" = hard centre-crop to 9:16 (old behaviour).
# Clips already close to 9:16 are always simply scaled+cropped to fill.
FIT_MODE = "blur"

# Colour grade -- the live WyrdEngine look (EFFECT_PROFILES.wyrd_fast): contrast
# 1.08, brightness x0.96, no sepia/vignette/grain. Set both to 1.0 to disable.
GRADE_CONTRAST = 1.08
GRADE_BRIGHTNESS = 0.96

# Caption: Luckiest Guy 80, white, 4px black stroke, 330px above bottom edge.
CAPTION_FONT = "Luckiest Guy"
CAPTION_FONT_SIZE = 80
CAPTION_COLOR = "#FFFFFF"
CAPTION_STROKE_COLOR = "#000000"
CAPTION_STROKE_WIDTH = 4
CAPTION_POSITION = "top"  # "top" or "bottom"
CAPTION_TOP_MARGIN = 300  # px from the top edge (clears the Shorts search/menu bar)
CAPTION_BOTTOM_MARGIN = 330  # used when CAPTION_POSITION = "bottom"
CAPTION_SIDE_MARGIN = 60
CAPTION_MAX_CHARS_PER_LINE = 22  # fallback only; wrapping is pixel-measured
CAPTION_START_SECONDS = 0.0
CAPTION_END_SECONDS = 3.0  # caption shows for the first 3 seconds only (None = whole clip)

# Optional title block (old channel style: Courier New 96 amber, 110px from top).
# Off by default -- it was for the folklore videos. Liberation Mono Bold is the
# bundled stand-in for Courier New.
TITLE_ENABLED = False
TITLE_TEXT = ""
TITLE_FONT = "Liberation Mono"
TITLE_FONT_SIZE = 96
TITLE_COLOR = "#FFBA08"
TITLE_STROKE_COLOR = "#000000"
TITLE_STROKE_WIDTH = 2
TITLE_TOP_MARGIN = 110
TITLE_SECONDS = 3.0

FONTS_DIR = "assets/fonts"
WATERMARK_PATH = "assets/watermark.png"  # supply your own logo here
WATERMARK_WIDTH = 275
WATERMARK_MARGIN_X = 160  # clears the Shorts Like/Share/Remix button column
WATERMARK_MARGIN_Y = 40

# Encode (same as WyrdEngine RENDER block)
VIDEO_CODEC = "libx264"
PRESET = "veryfast"
CRF = 22
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"

# --- Scheduling (informational -- actual schedule lives in the workflow YAML) ---
RUNS_PER_DAY = 2

# --- Approval gate ---
APPROVAL_TIMEOUT_HOURS = 6
APPROVAL_DEFAULT_ON_TIMEOUT = "reject"  # "reject" or "approve" -- start conservative

# Telegram-sent clips: post to YouTube only for now. Flip to True once Meta
# app review is approved to also post to Facebook + Instagram.
PUBLISH_META = False

# Outro appended to the end of every video (3s logo animation, 1080x1920).
OUTRO_ENABLED = True
OUTRO_PATH = "assets/outro.mp4"

# Subtitles (optional per video, turned on from Telegram). Narration is
# transcribed with Groq Whisper and burned in at the bottom, same font as the title.
SUBTITLE_MODEL = "whisper-large-v3-turbo"
SUBTITLE_FALLBACK_MODEL = "whisper-large-v3"  # tried if the first model is retired
SUBTITLE_FONT_SIZE = 72
SUBTITLE_BOTTOM_MARGIN = 330
SUBTITLE_MAX_LINES = 2
SUBTITLE_MAX_CHUNK_SECONDS = 3.5
SUBTITLE_NO_SPEECH_THRESHOLD = 0.6  # drop Whisper segments it thinks are not speech (music, noise)
