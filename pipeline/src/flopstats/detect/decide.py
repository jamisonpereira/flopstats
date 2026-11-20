"""Confirm / review / reject a verified flop by confidence."""

from __future__ import annotations

from typing import Literal

Status = Literal["confirmed", "review", "rejected", "ai_judged"]


def status(confidence: float, confirm_t: float, review_t: float, review_cap: int | None, review_count_so_far: int) -> Status:
    if confidence >= confirm_t:
        return "confirmed"
    if confidence < review_t:
        return "rejected"
    if review_cap is None or review_count_so_far < review_cap:
        return "review"  # with no cap, every borderline item goes to Jamison
    return "ai_judged"
