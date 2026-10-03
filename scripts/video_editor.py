"""
Crops/pads to vertical short format and overlays caption text + watermark
via ffmpeg. Requires ffmpeg installed on PATH (apt-get install ffmpeg in the
GitHub Actions runner -- see workflow YAML).
"""
import subprocess
from config import OUTPUT_RESOLUTION, WATERMARK_PATH, CAPTION_FONT_SIZE


def edit_video(input_path: str, output_path: str, caption: str) -> bool:
    width, height = OUTPUT_RESOLUTION

    # Escape characters ffmpeg's drawtext filter treats specially
    safe_caption = caption.replace("'", "\u2019").replace(":", "\\:")

    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}[scaled];"
        f"[scaled][1:v]overlay=W-w-40:H-h-40[watermarked];"
        f"[watermarked]drawtext=text='{safe_caption}':fontcolor=white:"
        f"fontsize={CAPTION_FONT_SIZE}:box=1:boxcolor=black@0.5:boxborderw=20:"
        f"x=(w-text_w)/2:y=120"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", WATERMARK_PATH,
        "-filter_complex", filter_complex,
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"ffmpeg failed: {result.stderr}")
        return False
    return True
