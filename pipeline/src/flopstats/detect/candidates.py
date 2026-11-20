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


def select(windows: list[WindowRow], threshold: float, prior_weight: float,
           max_len_s: float | None = None) -> list[Candidate]:
    """Windows at or over threshold, merged while they overlap or touch. With max_len_s, a run
    is split into pieces no longer than that (overlapping by one window), since a verifier
    reports one flop per clip and a long clip hides the rest."""
    out: list[Candidate] = []
    for w in sorted(windows, key=lambda w: w.start_s):
        fs = final_score(w.score, w.prior, prior_weight)
        if fs < threshold:
            continue
        last = out[-1] if out else None
        fits = last is not None and w.start_s <= last.end_s and (
            max_len_s is None or max(last.end_s, w.end_s) - last.start_s <= max_len_s)
        if fits:
            last.end_s = max(last.end_s, w.end_s)
            last.final_score = max(last.final_score, fs)
            last.windows.append(w)
        else:
            out.append(Candidate(w.start_s, w.end_s, fs, [w]))
    return out
