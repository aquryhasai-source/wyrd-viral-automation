"""
Turns a raw clip into a 1080x1920 short in the Wyrd Echoes house style.

Look and caption settings are ported from WyrdEngine_v1 (see config.py):
contrast 1.08 / brightness x0.96 grade, Luckiest Guy 80 white caption with a
4px black stroke sitting 330px above the bottom edge, optional amber title,
libx264 veryfast crf 22, AAC 192k, faststart.

One ffmpeg pass: fit -> grade -> watermark -> burned-in ASS captions.
Requires ffmpeg/ffprobe with libass on PATH (apt-get install ffmpeg).
"""
import json
import os
import re
import subprocess
import tempfile
import textwrap

import config as cfg

_EMOJI_RE = re.compile(
    "[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D\u2B50\u2B06\u2194-\u21AA\u231A-\u23FF]"
)


# ---------------------------------------------------------------- probing
def _probe(path: str) -> dict | None:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"ffprobe failed: {r.stderr[-500:]}")
        return None
    data = json.loads(r.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        print("No video stream found")
        return None
    has_audio = any(s.get("codec_type") == "audio" for s in data["streams"])
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    rotation = int(video.get("tags", {}).get("rotate", rotation) or rotation)
    w, h = int(video["width"]), int(video["height"])
    if abs(rotation) in (90, 270):  # ffmpeg auto-rotates; report display size
        w, h = h, w
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    return {"w": w, "h": h, "duration": duration, "has_audio": has_audio}


# ---------------------------------------------------------------- captions
def _ass_color(value: str) -> str:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Bad colour: {value}")
    return f"&H00{v[4:6]}{v[2:4]}{v[0:2]}".upper().replace("&H", "&H")


def _clean_text(text: str) -> str:
    text = _EMOJI_RE.sub("", text or "")  # Luckiest Guy has no emoji glyphs
    return re.sub(r"\s+", " ", text).strip()


def _wrap(text: str, font_file: str, size: int, max_px: int, fallback_chars: int) -> list[str]:
    """Wrap by measured pixel width (Luckiest Guy is wide; char counts overflow)."""
    words = text.split()
    if not words:
        return [""]
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(os.path.join(cfg.FONTS_DIR, font_file), size)
        # ~6% headroom for libass faux-bold + outline
        limit = max_px * 0.94
        width = lambda t: font.getlength(t)
    except Exception:
        limit = fallback_chars
        width = len
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if width(trial) <= limit:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _ass_text(lines: list[str]) -> str:
    esc = [l.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}") for l in lines]
    return r"\N".join(esc)


def _ass_time(sec: float) -> str:
    cs = int(round(sec * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _write_ass(path: str, caption: str, duration: float) -> None:
    width, height = cfg.OUTPUT_RESOLUTION
    caption = _clean_text(caption)
    text_px = width - 2 * cfg.CAPTION_SIDE_MARGIN
    cap_start = float(cfg.CAPTION_START_SECONDS)
    cap_end = cfg.CAPTION_END_SECONDS
    cap_end = duration if cap_end is None else min(float(cap_end), duration)

    # Bold=-1 matches the old engine's style lines exactly.
    top = cfg.CAPTION_POSITION == "top"
    cap_align = 8 if top else 2  # ASS numpad alignment: 8 = top-centre, 2 = bottom-centre
    cap_margin_v = cfg.CAPTION_TOP_MARGIN if top else cfg.CAPTION_BOTTOM_MARGIN
    cap_style = (
        f"Style: Caption,{cfg.CAPTION_FONT},{cfg.CAPTION_FONT_SIZE},"
        f"{_ass_color(cfg.CAPTION_COLOR)},&H00000000,{_ass_color(cfg.CAPTION_STROKE_COLOR)},&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,{cfg.CAPTION_STROKE_WIDTH},0,{cap_align},"
        f"{cfg.CAPTION_SIDE_MARGIN},{cfg.CAPTION_SIDE_MARGIN},{cap_margin_v},1"
    )
    title_style = (
        f"Style: Title,{cfg.TITLE_FONT},{cfg.TITLE_FONT_SIZE},"
        f"{_ass_color(cfg.TITLE_COLOR)},&H00000000,{_ass_color(cfg.TITLE_STROKE_COLOR)},&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,{cfg.TITLE_STROKE_WIDTH},0,8,"
        f"{cfg.CAPTION_SIDE_MARGIN},{cfg.CAPTION_SIDE_MARGIN},{cfg.TITLE_TOP_MARGIN},1"
    )

    out = [
        "[Script Info]", "ScriptType: v4.00+",
        f"PlayResX: {width}", f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding",
        cap_style, title_style, "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    if caption and cap_end > cap_start:
        out.append(
            f"Dialogue: 0,{_ass_time(cap_start)},{_ass_time(cap_end)},Caption,,0,0,0,,"
            f"{_ass_text(_wrap(caption, 'LuckiestGuy-Regular.ttf', cfg.CAPTION_FONT_SIZE, text_px, cfg.CAPTION_MAX_CHARS_PER_LINE))}"
        )
    title = _clean_text(cfg.TITLE_TEXT)
    if cfg.TITLE_ENABLED and title:
        t_end = min(float(cfg.TITLE_SECONDS), duration)
        out.append(
            f"Dialogue: 0,{_ass_time(0)},{_ass_time(t_end)},Title,,0,0,0,,"
            f"{_ass_text(_wrap(title, 'LiberationMono-Bold.ttf', cfg.TITLE_FONT_SIZE, text_px, 16))}"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- filters
def _video_chain(src_w: int, src_h: int, wm_idx: int | None) -> str:
    """Fit -> grade -> watermark -> burned-in captions. Produces [main_v]."""
    W, H = cfg.OUTPUT_RESOLUTION
    src_ratio, tgt_ratio = src_w / src_h, W / H
    near_vertical = abs(src_ratio - tgt_ratio) / tgt_ratio < 0.06

    if near_vertical or cfg.FIT_MODE == "crop":
        fit = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1[fit]"
        )
    else:
        fit = (
            f"[0:v]split[bgsrc][fgsrc];"
            f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=30:5,eq=brightness=-0.12[bg];"
            f"[fgsrc]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[fit]"
        )

    grade = (
        f"[fit]eq=contrast={cfg.GRADE_CONTRAST},"
        f"colorchannelmixer=rr={cfg.GRADE_BRIGHTNESS}:gg={cfg.GRADE_BRIGHTNESS}:bb={cfg.GRADE_BRIGHTNESS},"
        f"fps={cfg.FPS},format=yuv420p[graded]"
    )

    if wm_idx is not None:
        wm = (
            f"[{wm_idx}:v]scale={cfg.WATERMARK_WIDTH}:-1[wm];"
            f"[graded][wm]overlay=W-w-{cfg.WATERMARK_MARGIN_X}:H-h-{cfg.WATERMARK_MARGIN_Y}[marked]"
        )
        last = "marked"
    else:
        wm, last = "", "graded"

    subs = (
        f"[{last}]subtitles=filename=captions.ass:"
        f"fontsdir='{os.path.abspath(cfg.FONTS_DIR)}'[main_v]"
    )
    return ";".join(p for p in (fit, grade, wm, subs) if p)


# ---------------------------------------------------------------- public API
def edit_video(input_path: str, output_path: str, caption: str) -> bool:
    info = _probe(input_path)
    if not info or info["duration"] <= 0:
        return False

    W, H = cfg.OUTPUT_RESOLUTION
    D = info["duration"]  # no length cap: the whole clip is kept

    use_watermark = os.path.exists(cfg.WATERMARK_PATH)
    if not use_watermark:
        print(f"Watermark not found at {cfg.WATERMARK_PATH}; continuing without it")

    outro_info = None
    if cfg.OUTRO_ENABLED:
        if os.path.exists(cfg.OUTRO_PATH):
            outro_info = _probe(cfg.OUTRO_PATH)
            if not outro_info or outro_info["duration"] <= 0:
                print("Outro could not be read; continuing without it")
                outro_info = None
        else:
            print(f"Outro not found at {cfg.OUTRO_PATH}; continuing without it")

    # --- inputs (indexes follow the order they are added) ---
    inputs = [os.path.abspath(input_path)]
    extra_flags: dict[int, list[str]] = {}
    nxt = 1
    wm_idx = None
    if use_watermark:
        inputs.append(os.path.abspath(cfg.WATERMARK_PATH))
        wm_idx, nxt = nxt, nxt + 1
    outro_idx = None
    if outro_info:
        inputs.append(os.path.abspath(cfg.OUTRO_PATH))
        outro_idx, nxt = nxt, nxt + 1
    sil_idx = None
    if not info["has_audio"] or (outro_info and not outro_info["has_audio"]):
        inputs.append("anullsrc=r=44100:cl=stereo")
        extra_flags[nxt] = ["-f", "lavfi"]
        sil_idx, nxt = nxt, nxt + 1

    work = tempfile.mkdtemp(prefix="wyrd_edit_")
    try:
        _write_ass(os.path.join(work, "captions.ass"), caption, D)
        parts = [_video_chain(info["w"], info["h"], wm_idx)]

        # main segment: trimmed to exactly D so audio/video stay in step at the join
        parts.append(f"[main_v]trim=duration={D:.3f},setpts=PTS-STARTPTS[mv]")
        if info["has_audio"]:
            parts.append(
                f"[0:a:0]aresample=44100,aformat=channel_layouts=stereo,"
                f"apad,atrim=duration={D:.3f},asetpts=PTS-STARTPTS[ma]"
            )
        else:
            parts.append(f"[{sil_idx}:a]atrim=duration={D:.3f},asetpts=PTS-STARTPTS[ma]")

        if outro_info:
            OD = outro_info["duration"]
            parts.append(
                f"[{outro_idx}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={cfg.FPS},format=yuv420p,"
                f"trim=duration={OD:.3f},setpts=PTS-STARTPTS[ov]"
            )
            if outro_info["has_audio"]:
                parts.append(
                    f"[{outro_idx}:a:0]aresample=44100,aformat=channel_layouts=stereo,"
                    f"apad,atrim=duration={OD:.3f},asetpts=PTS-STARTPTS[oa]"
                )
            else:
                parts.append(f"[{sil_idx}:a]atrim=duration={OD:.3f},asetpts=PTS-STARTPTS[oa]")
            parts.append("[mv][ma][ov][oa]concat=n=2:v=1:a=1[outv][outa]")
        else:
            parts.append("[mv]null[outv];[ma]anull[outa]")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for i, path in enumerate(inputs):
            cmd += extra_flags.get(i, []) + ["-i", path]
        cmd += [
            "-filter_complex", ";".join(parts),
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", cfg.VIDEO_CODEC, "-preset", cfg.PRESET, "-crf", str(cfg.CRF),
            "-pix_fmt", "yuv420p", "-r", str(cfg.FPS),
            "-c:a", cfg.AUDIO_CODEC, "-b:a", cfg.AUDIO_BITRATE, "-ar", "44100",
            "-movflags", "+faststart",
            os.path.abspath(output_path),
        ]
        # cwd = work dir so the subtitles filter can use a plain relative filename
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, cwd=work)
        if r.returncode != 0:
            print(f"ffmpeg failed (tail): {r.stderr[-1500:]}")
            return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    finally:
        for name in os.listdir(work):
            try:
                os.remove(os.path.join(work, name))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
