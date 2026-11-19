"""Match-data priors: windows near fouls, cards, penalties, VAR checks and injury subs get a
0-1 boost. A prior only ever raises a window's score (see candidates.final_score)."""

from __future__ import annotations

from dataclasses import dataclass

from flopstats.video.timesync import HALF_S, SyncResult

FULL_S = 30.0
ZERO_S = 90.0
NON_FOUL_CARD_COMMENTS = {"argument", "dissent", "entering field", "leaving field", "unsportsmanlike conduct"}


@dataclass(frozen=True)
class MatchEvent:
    minute: int | None
    extra_minute: int | None
    type: str
    detail: str | None
    comments: str | None


def _qualifies(e: MatchEvent) -> bool:
    kind, detail, comments = (e.type or "").lower(), (e.detail or "").lower(), (e.comments or "").lower()
    if kind == "card":
        return comments not in NON_FOUL_CARD_COMMENTS
    if kind == "goal":
        return "penalty" in detail
    if kind == "var":
        return True
    if kind == "subst":
        return "injur" in comments
    return False


def event_video_time(e: MatchEvent, sync: SyncResult) -> float | None:
    """Video second of an event. API minutes are "elapsed" (minute 20 = 19:00-20:00), so use
    the middle of the minute; 45+x stays in the first half."""
    if sync.status != "ok" or e.minute is None:
        return None
    clock_min = e.minute + (e.extra_minute or 0) - 0.5
    if e.minute <= 45:
        return sync.kickoff_offset_s + clock_min * 60
    return sync.second_half_offset_s + (clock_min - 45) * 60


def _boost(distance_s: float) -> float:
    if distance_s <= FULL_S:
        return 1.0
    if distance_s >= ZERO_S:
        return 0.0
    return 1.0 - (distance_s - FULL_S) / (ZERO_S - FULL_S)


def window_priors(events: list[MatchEvent], lineups, sync: SyncResult, windows: list[tuple[float, float]]) -> list[float]:
    """One prior per window. `lineups` is accepted for future per-player priors; unused now."""
    times = [t for t in (event_video_time(e, sync) for e in events if _qualifies(e)) if t is not None]
    out = []
    for start, end in windows:
        best = 0.0
        for t in times:
            distance = 0.0 if start <= t <= end else min(abs(t - start), abs(t - end))
            best = max(best, _boost(distance))
        out.append(best)
    return out
