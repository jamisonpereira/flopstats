"""Turn scored windows into candidates: apply the prior, threshold, merge overlaps."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WindowRow:
    start_s: float
    end_s: float
    score: float
    prior: float = 0.0
    id: int | None = None


@dataclass
class Candidate:
    start_s: float
    end_s: float
    final_score: float
    windows: list[WindowRow] = field(default_factory=list)


def final_score(score: float, prior: float, prior_weight: float) -> float:
    """score + prior_weight * prior, clipped to 1; never below the model's own score."""
    return min(1.0, max(score, score + prior_weight * prior))


def select(windows: list[WindowRow], threshold: float, prior_weight: float) -> list[Candidate]:
    out: list[Candidate] = []
    for w in sorted(windows, key=lambda w: w.start_s):
        fs = final_score(w.score, w.prior, prior_weight)
        if fs < threshold:
            continue
        if out and w.start_s <= out[-1].end_s:  # overlapping or adjacent: same moment
            c = out[-1]
            c.end_s = max(c.end_s, w.end_s)
            c.final_score = max(c.final_score, fs)
            c.windows.append(w)
        else:
            out.append(Candidate(w.start_s, w.end_s, fs, [w]))
    return out
