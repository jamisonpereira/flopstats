"""Map video time <-> game time from the broadcast's on-screen clock.

Sample frames evenly (skipping the first and last 2 minutes), let a ClockReader read the
clock, and turn each reading into a candidate offset for the half it belongs to:
first half: kickoff = t - clock; second half: start = t - (clock - 45:00). The densest
cluster of candidates within ±3 s wins and its median is the offset. Each half needs at
least 5 agreeing readings, otherwise the video is `needs_review`: a wrong offset is never
guessed (Review Focus #2).
"""

from __future__ import annotations

import statistics
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from flopstats.video import ffmpeg

HALF_S = 45 * 60
MAX_FIRST_HALF_STOPPAGE_S = 10 * 60
AGREE_S = 3.0
MIN_AGREEING = 5
MIN_CONFIDENCE = 0.5
EDGE_S = 120.0


@dataclass(frozen=True)
class ClockReading:
    minute: int
    second: int
    confidence: float


class ClockReader(Protocol):
    def read(self, png: Path) -> ClockReading | None: ...


@dataclass(frozen=True)
class SyncResult:
    kickoff_offset_s: float | None
    second_half_offset_s: float | None
    status: Literal["ok", "needs_review"]


def sample_times(duration_s: float, samples: int) -> list[float]:
    lo, hi = EDGE_S, duration_s - EDGE_S
    if hi <= lo or samples < 1:
        return []
    if samples == 1:
        return [(lo + hi) / 2]
    step = (hi - lo) / (samples - 1)
    return [round(lo + i * step, 3) for i in range(samples)]


def _cluster(candidates: list[float]) -> list[float]:
    """The largest group of candidates within ±AGREE_S of one of them."""
    best: list[float] = []
    for c in candidates:
        group = [x for x in candidates if abs(x - c) <= AGREE_S]
        if len(group) > len(best):
            best = group
    return best


def sync(
    video_path,
    duration_s: float,
    reader: ClockReader,
    samples: int = 24,
    *,
    extract: Callable[[Path, float, Path], Path] = ffmpeg.frame_at,
) -> SyncResult:
    first: list[float] = []
    second: list[float] = []
    with tempfile.TemporaryDirectory(prefix="flopstats-sync-") as tmp:
        for i, t in enumerate(sample_times(duration_s, samples)):
            png = extract(Path(video_path), t, Path(tmp) / f"sample_{i:03d}.png")
            reading = reader.read(png)
            if reading is None or reading.confidence < MIN_CONFIDENCE:
                continue
            clock = reading.minute * 60 + reading.second
            if clock <= HALF_S + MAX_FIRST_HALF_STOPPAGE_S:
                first.append(t - clock)
            if clock >= HALF_S:
                second.append(t - (clock - HALF_S))

    def fit(cands: list[float]) -> float | None:
        group = _cluster(cands)
        return statistics.median(group) if len(group) >= MIN_AGREEING else None

    kickoff, second_half = fit(first), fit(second)
    if kickoff is not None and second_half is not None and second_half < kickoff + HALF_S:
        kickoff = second_half = None  # inconsistent: the second half can't start before 45 min of play
    status = "ok" if kickoff is not None and second_half is not None else "needs_review"
    return SyncResult(kickoff, second_half, status)


def to_game_time(video_t: float, sync: SyncResult) -> tuple[int, int] | None:
    if sync.status != "ok":
        return None
    if video_t >= sync.second_half_offset_s:
        clock = HALF_S + (video_t - sync.second_half_offset_s)
    elif video_t >= sync.kickoff_offset_s:
        clock = video_t - sync.kickoff_offset_s
    else:
        return None
    m, s = divmod(int(round(clock)), 60)
    return m, s


def to_video_time(minute: int, second: int, sync: SyncResult) -> float | None:
    if sync.status != "ok":
        return None
    clock = minute * 60 + second
    if clock < HALF_S:
        return sync.kickoff_offset_s + clock
    return sync.second_half_offset_s + (clock - HALF_S)
