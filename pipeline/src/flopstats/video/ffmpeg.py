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
