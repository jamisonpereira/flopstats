"""One incident per real-world moment: collapse replays and overlapping-window repeats."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from flopstats.detect.verify import VerifyResult

KEY_ROUND_S = 15
SAME_MOMENT_S = 15
REPLAY_WINDOW_S = 120


@dataclass(frozen=True)
class Placed:
    """A verifier result placed on the full video's timeline."""

    result: VerifyResult
    video_start_s: float  # where the candidate's segment starts in the video
    candidate_id: int | None = None

    @property
    def abs_start_s(self) -> float:
        return self.video_start_s + self.result.start_s


def key(result: VerifyResult, video_start_s: float) -> str:
    start = math.floor((video_start_s + result.start_s) / KEY_ROUND_S + 0.5) * KEY_ROUND_S
    f = result.flopper
    shirt = str(f.shirt_number) if f.shirt_number is not None else "?"
    if f.shirt_number is None and f.name:  # keep two named-but-unnumbered floppers apart
        shirt += ":" + re.sub(r"[^a-z0-9]+", "-", f.name.casefold()).strip("-")
    return f"{start}:{f.team or '?'}:{shirt}"


def _same_flopper(a: VerifyResult, b: VerifyResult) -> bool:
    """Could these be the same player? Unknown fields are compatible; only known, different
    values (team, shirt number, or name when neither has a number) tell two players apart."""
    fa, fb = a.flopper, b.flopper
    if fa.team and fb.team and fa.team != fb.team:
        return False
    if fa.shirt_number is not None and fb.shirt_number is not None:
        return fa.shirt_number == fb.shirt_number
    if fa.name and fb.name and fa.shirt_number is None and fb.shirt_number is None:
        return fa.name.casefold() == fb.name.casefold()
    return True


def collapse(items: list[Placed]) -> list[Placed]:
    ordered = sorted(items, key=lambda p: p.abs_start_s)
    originals = [p for p in ordered if not p.result.is_replay]
    kept: list[Placed] = []
    for p in ordered:
        if p.result.is_replay and any(
            _same_flopper(p.result, o.result) and abs(p.abs_start_s - o.abs_start_s) <= REPLAY_WINDOW_S for o in originals
        ):
            continue  # a replay of an incident we already have
        if any(_same_flopper(p.result, k.result) and abs(p.abs_start_s - k.abs_start_s) <= SAME_MOMENT_S for k in kept):
            continue  # the same moment seen again (overlapping candidates): keep the earliest
        kept.append(p)
    return kept
