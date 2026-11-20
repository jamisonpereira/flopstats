"""Thin ffmpeg/ffprobe helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise FFmpegError(f"{args[0]} failed: " + " | ".join(tail))
    return proc.stdout


def probe_duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip())


def cut(src: Path, start_s: float, end_s: float, dest: Path, reencode: bool, *, audio: bool = False) -> Path:
    """Cut [start_s, end_s) from src.

    reencode=True: H.264 720p (`libx264 -preset veryfast -crf 26`); audio dropped for model
    segments, or kept as AAC 96k when audio=True (clips). reencode=False: stream copy
    (fast, cut points snap to keyframes).
    """
    if end_s <= start_s or start_s < 0:
        raise ValueError(f"bad cut range {start_s}..{end_s}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start_s:.3f}", "-i", str(src), "-t", f"{end_s - start_s:.3f}"]
    if reencode:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-vf", "scale=-2:720", "-pix_fmt", "yuv420p"]
        args += ["-c:a", "aac", "-b:a", "96k"] if audio else ["-an"]
        args += ["-movflags", "+faststart"]
    else:
        args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    _run(args + [str(dest)])
    return dest


def frame_at(src: Path, t_s: float, dest_png: Path) -> Path:
    dest_png = Path(dest_png)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_s:.3f}", "-i", str(src), "-frames:v", "1", str(dest_png)])
    if not dest_png.exists():
        raise FFmpegError(f"no frame at {t_s}s in {src}")
    return dest_png


# --- working copy: encode a match once, then copy windows out of it -----------------------

# Keyframes land a hair after each window start (the first frame's timestamp); a window cut
# starts this far after its nominal start so a stream copy begins exactly on that keyframe.
KEY_NUDGE_S = 0.1
WORK_BITRATE = "2000k"


def has_videotoolbox() -> bool:
    """True when this ffmpeg can decode, scale and encode on Apple's media engine."""
    try:
        enc = _run(["ffmpeg", "-hide_banner", "-encoders"])
        flt = _run(["ffmpeg", "-hide_banner", "-filters"])
    except (FFmpegError, OSError):
        return False
    return "h264_videotoolbox" in enc and "scale_vt" in flt


def working_copy(src: Path, dest: Path, *, keyframe_s: float, fps: float = 25, height: int = 720,
                 hw: bool | None = None) -> Path:
    """Video-only H.264 copy of a match at `height`p / `fps`, with a keyframe every `keyframe_s`
    seconds, so each scoring window is a stream copy (see `window`). hw=None: use the Apple media
    engine when available (Mac: ~18x real time at 25 fps), else libx264 on the CPU."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    use_hw = has_videotoolbox() if hw is None else hw
    keys = ["-force_key_frames", f"expr:gte(t,n_forced*{keyframe_s})"]
    if use_hw:
        args = ["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld",
                "-i", str(src), "-an", "-vf", f"scale_vt=w=-2:h={height}", "-r", f"{fps:g}",
                "-c:v", "h264_videotoolbox", "-b:v", WORK_BITRATE, "-g", str(int(fps * keyframe_s * 10))]
    else:
        args = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", f"scale=-2:{height}", "-r", f"{fps:g}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p"]
    tmp = dest.with_name(dest.stem + ".tmp.mp4")
    _run(args + keys + ["-movflags", "+faststart", str(tmp)])
    tmp.replace(dest)
    return dest


def window(work: Path, start_s: float, end_s: float, dest: Path) -> Path:
    """[start_s, end_s) of a working copy as a stream copy (no re-encode, ~0.05 s)."""
    return cut(work, start_s + KEY_NUDGE_S, end_s + KEY_NUDGE_S, dest, reencode=False)
