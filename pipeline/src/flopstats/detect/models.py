"""Model interfaces. Adapters (gemini.py, other vendors) implement these, so the model for
each stage can be swapped per detection run."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from flopstats.video.timesync import ClockReader, ClockReading  # re-exported

__all__ = ["ClockReader", "ClockReading", "ScoreResult", "WindowScorer", "Verifier"]


@dataclass(frozen=True)
class ScoreResult:
    p_flop: float
    usd: Decimal
    raw: dict = field(default_factory=dict)


class WindowScorer(Protocol):
    name: str

    def score(self, segment: Path) -> ScoreResult: ...


class Verifier(Protocol):
    name: str

    def verify(self, segment: Path, context: Any) -> Any: ...  # VerifyContext -> VerifyResult (Task 13)
