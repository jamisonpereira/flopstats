"""Overlapping time windows over a video (the wide net's unit of work)."""

from __future__ import annotations


def make(duration_s: float, length_s: float = 20, step_s: float = 10) -> list[tuple[float, float]]:
    """Windows of `length_s` every `step_s`; the last one is clipped to the duration."""
    if duration_s <= 0 or length_s <= 0 or step_s <= 0:
        raise ValueError("duration, length and step must be positive")
    out: list[tuple[float, float]] = []
    start = 0.0
    while True:
        end = min(start + length_s, duration_s)
        out.append((_num(start), _num(end)))
        if end >= duration_s:
            return out
        start += step_s


def _num(x: float) -> float:
    return int(x) if float(x).is_integer() else round(x, 3)
