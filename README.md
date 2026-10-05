# WYRD VIRAL Automation

Automated trending-clip repost pipeline. Runs entirely on GitHub Actions +
a tiny Cloudflare Worker — no VM, no server to maintain. $0/month on free
tiers.

See `wyrd-viral-pivot-spec.md` (shared separately) for the full design
rationale. This README is the practical setup checklist.

---

## How it works

1. **`discover.yml`** runs twice daily, finds a candidate clip, downloads it,
   generates a reactive caption, edits it (crop + watermark + caption text),
   uploads it to Supabase Storage, and sends you a Telegram message with the
   video and Approve/Reject buttons.
2. You tap a button on your phone.
3. The **Cloudflare Worker** receives Telegram's webhook call and tells
   GitHub to run **`publish.yml`**, which either posts the clip to YouTube,
   Facebook, and Instagram (approve) or deletes it (reject).
4. **`timeout_sweep.yml`** runs hourly and auto-resolves anything you didn't
   respond to within `config.APPROVAL_TIMEOUT_HOURS` (default: reject).

---

## One-time setup

### 1. Push this repo to GitHub
```
cd wyrd-viral-automation
git init
git add .
git commit -m "Initial pipeline scaffold"
git branch -M main
git remote add origin https://github.com/<you>/wyrd-viral-automation.git
git push -u origin main
```

### 2. Create a Supabase table and storage bucket
In your existing Supabase project's SQL editor, run the `create table wyrd_viral_posts (...)`
statement from the top of `scripts/db.py`.

Then in Storage, create a **public** bucket named `wyrd-viral-pending-clips`.

### 3. Reddit — nothing to set up
Clip discovery uses Reddit's public `.json` endpoints, which need no registered
app or credentials. (Reddit has recently made new "script" app creation
unreliable for many accounts, so this sidesteps that entirely.)

### 4. YouTube API access
Two separate things needed:
- **API key** (read-only, for polling MrBeast's channel): Google Cloud Console
  → APIs & Services → Credentials → Create API Key
- **OAuth refresh token** (for uploading to your channel): enable the YouTube
  Data API v3, create an OAuth 2.0 Client ID (Desktop app type), then run a
  one-time local script using `google-auth-oauthlib` to complete the consent
  flow and print a refresh token. Happy to generate that one-time script if
  you want it.

### 5. Telegram bot
- Message **@BotFather** on Telegram → `/newbot` → follow the prompts → copy
  the bot token
- Message your new bot once, then visit
  `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your numeric chat ID

### 6. GitHub Personal Access Token (for the Worker)
- GitHub → Settings → Developer settings → Fine-grained tokens → generate one
  scoped only to this repo, with **Contents: Read** and **Actions: Read and write**

### 7. Deploy the Cloudflare Worker
```
cd cloudflare-worker
npm install -g wrangler
wrangler login
wrangler deploy
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put GITHUB_TOKEN
wrangler secret put GITHUB_REPO   # e.g. yourusername/wyrd-viral-automation
```
Then register the webhook once (replace both placeholders):
```
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<your-worker-url>"
```

### 8. Meta (Facebook/Instagram) app
- developers.facebook.com → Create App → add **Pages API** and
  **Instagram Graph API** products
- Submit for permissions review (`pages_manage_posts`, `instagram_content_publish`)
  — this can take days to weeks, so start it early. YouTube can go live on its
  own while this is pending.

### 9. Add all secrets to GitHub
Repo → Settings → Secrets and variables → Actions → New repository secret,
for each of:
```
YOUTUBE_API_KEY, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
GROQ_API_KEY
SUPABASE_URL, SUPABASE_KEY
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
META_PAGE_ID, META_PAGE_ACCESS_TOKEN, META_IG_BUSINESS_ACCOUNT_ID
```

### 10. Replace the placeholder watermark
`assets/watermark.png` is currently a plain placeholder box — swap in your
actual logo (transparent PNG, roughly 300x100px works well).

### 11. Test it
Go to the Actions tab → "Discover and Queue Clip" → **Run workflow** (manual
trigger) to test end-to-end without waiting for the schedule.

---

## Known limitations (see spec for full detail)

- Processes one candidate per run — raise the limit in `main_discover.py`
  once you trust the filter rules
- yt-dlp reliably handles YouTube and most Reddit-linked video hosts, not
  Instagram/TikTok directly
- Copyright strikes remain possible regardless of the filter — this reduces
  risk, it doesn't eliminate it

---

## Video look (ported from WyrdEngine_v1)

All values live in `config.py`: Luckiest Guy 80 white caption with 4px black
stroke, at the top of the frame (300px down) for the first 3 seconds only; contrast 1.08 / brightness x0.96 grade;
libx264 veryfast crf 22; AAC 192k; faststart. Fonts are bundled in
`assets/fonts/`. Landscape clips get a blurred fill (`FIT_MODE = "crop"` for the
old hard crop).

## Telegram flow (video -> questions -> preview -> approve -> YouTube)

1. Send the bot a video. It asks, in order: TITLE (the YouTube title), DESCRIPTION, TAGS,
   then two tap questions: show the TITLE on the video (top, first 3 seconds) On/Off, and
   SUBTITLES from the narration On/Off.
2. GitHub Actions renders the video (grade, watermark, optional title, optional subtitles,
   3-second outro) and sends it back to you with Approve / Reject buttons. Nothing is
   posted yet. Previews not answered within `APPROVAL_TIMEOUT_HOURS` (6) are discarded.
3. Approve uploads to YouTube Shorts with your title, description and tags. Reject deletes
   the preview. Facebook/Instagram stay off (`PUBLISH_META = False`) until Meta approves.

Subtitles work like WyrdEngine_v1: faster-whisper "small" (CPU, int8, word timestamps, VAD
filter), one word on screen at a time at its exact timing, Luckiest Guy 80 at the bottom. If
the local model fails, Groq Whisper is the fallback. Settings are in `config.py` (`SUBTITLE_*`). `/cancel` aborts a conversation. One-time worker setup:

    cd cloudflare-worker
    wrangler kv namespace create SESSIONS     # paste the id into wrangler.toml
    wrangler secret put ALLOWED_CHAT_ID       # recommended
    wrangler deploy
