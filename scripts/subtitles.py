"""
Narration -> subtitle cues, using Groq's hosted Whisper.

transcribe_cues(video_path) returns (cues, reason):
  cues   -- list of (start_s, end_s, text), [] if no speech was found,
            or None if transcription failed
  reason -- short human-readable note for the Telegram message

Requires env var GROQ_API_KEY and ffmpeg on PATH.
"""
import os
import subprocess
import tempfile

import requests

import config as cfg
from scripts.video_editor import _probe, _wrap, _clean_text

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def _extract_audio(video_path: str, out_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", out_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def _call_whisper(audio_path: str, model: str) -> requests.Response:
    with open(audio_path, "rb") as f:
        return requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
            data=[
                ("model", model),
                ("response_format", "verbose_json"),
                ("temperature", "0"),
                ("timestamp_granularities[]", "word"),
                ("timestamp_granularities[]", "segment"),
            ],
            timeout=180,
        )


def _speech_words(result: dict) -> list[tuple[float, float, str]]:
    """Words that fall inside segments Whisper considers real speech."""
    good = []
    for seg in result.get("segments", []) or []:
        if seg.get("no_speech_prob", 0.0) > cfg.SUBTITLE_NO_SPEECH_THRESHOLD:
            continue
        if seg.get("avg_logprob", 0.0) < -1.2:  # low confidence: usually music or noise
            continue
        good.append((seg["start"], seg["end"]))
    words = []
    for w in result.get("words", []) or []:
        mid = (w["start"] + w["end"]) / 2
        if not good or any(s - 0.05 <= mid <= e + 0.05 for s, e in good):
            words.append((float(w["start"]), float(w["end"]), w["word"].strip()))
    # No word-level data returned: fall back to whole segments
    if not words:
        for seg in result.get("segments", []) or []:
            if (seg.get("no_speech_prob", 0.0) <= cfg.SUBTITLE_NO_SPEECH_THRESHOLD
                    and seg.get("avg_logprob", 0.0) >= -1.2 and seg.get("text", "").strip()):
                words.append((float(seg["start"]), float(seg["end"]), seg["text"].strip()))
    return [w for w in words if w[2]]


def _chunk(words: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Group words into short on-screen phrases (at most SUBTITLE_MAX_LINES lines)."""
    W, _ = cfg.OUTPUT_RESOLUTION
    text_px = W - 2 * cfg.CAPTION_SIDE_MARGIN
    cues, cur = [], []

    def fits(ws):
        text = _clean_text(" ".join(x[2] for x in ws))
        lines = _wrap(text, "LuckiestGuy-Regular.ttf", cfg.SUBTITLE_FONT_SIZE, text_px, 20)
        return len(lines) <= cfg.SUBTITLE_MAX_LINES

    def flush():
        if cur:
            text = _clean_text(" ".join(x[2] for x in cur))
            if text:
                cues.append([cur[0][0], cur[-1][1], text])

    for w in words:
        if cur:
            gap = w[0] - cur[-1][1]
            too_long = (w[1] - cur[0][0]) > cfg.SUBTITLE_MAX_CHUNK_SECONDS
            ends_sentence = cur[-1][2].endswith((".", "?", "!"))
            if gap > 0.7 or too_long or ends_sentence or not fits(cur + [w]):
                flush()
                cur = []
        cur.append(w)
    flush()

    # Keep each cue on screen until the next one starts (min 0.4s), no overlaps
    for i, c in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else None
        c[1] = max(c[1], c[0] + 0.4)
        if nxt is not None:
            c[1] = min(c[1] + 0.25, nxt)
    return [tuple(c) for c in cues if c[1] > c[0]]


def transcribe_cues(video_path: str):
    info = _probe(video_path)
    if not info or not info["has_audio"]:
        return [], "the clip has no audio track"
    if not os.environ.get("GROQ_API_KEY"):
        return None, "GROQ_API_KEY is not set"

    work = tempfile.mkdtemp(prefix="wyrd_stt_")
    audio = os.path.join(work, "audio.mp3")
    try:
        if not _extract_audio(video_path, audio):
            return None, "could not extract the audio"
        resp = _call_whisper(audio, cfg.SUBTITLE_MODEL)
        if resp.status_code in (400, 404) and cfg.SUBTITLE_FALLBACK_MODEL:
            print(f"Whisper model {cfg.SUBTITLE_MODEL} failed ({resp.status_code}): {resp.text[:300]}")
            resp = _call_whisper(audio, cfg.SUBTITLE_FALLBACK_MODEL)
        if not resp.ok:
            print(f"Whisper error {resp.status_code}: {resp.text[:500]}")
            return None, f"Groq transcription failed ({resp.status_code})"
        words = _speech_words(resp.json())
        if not words:
            return [], "no speech was detected"
        return _chunk(words), "ok"
    except Exception as e:  # network, JSON, ffmpeg timeouts...
        print(f"Transcription error: {e}")
        return None, "transcription error"
    finally:
        for n in os.listdir(work):
            try:
                os.remove(os.path.join(work, n))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
