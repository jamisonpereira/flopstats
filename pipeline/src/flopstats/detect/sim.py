"""SIM Rating: per-flop score and per-entity (player/team/...) index. All weights are settings."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import psycopg

DEFAULT_CONTACT = {"none": 1.5, "light": 1.0, "real": 0.5}
DEFAULT_PAYOFF = {"nothing": 1.0, "foul": 1.2, "opponent_booked": 1.5, "penalty_won": 2.0, "penalty_scored": 2.5}


@dataclass(frozen=True)
class SimWeights:
    base: float = 10.0
    contact: dict = field(default_factory=lambda: dict(DEFAULT_CONTACT))
    payoff: dict = field(default_factory=lambda: dict(DEFAULT_PAYOFF))
    ground_scale_s: float = 10.0
    roll_bonus: float = 0.05
    max_rolls: int = 5
    miracle_bonus: float = 0.1
    default_fake_pain: int = 5
    min_minutes: int = 270

    @classmethod
    def load(cls, conn: psycopg.Connection) -> SimWeights:
        """Defaults, overridden by the `settings` row `sim_weights` (dicts merge key by key)."""
        row = conn.execute("select value from settings where key = 'sim_weights'").fetchone()
        w = cls()
        if not row or not isinstance(row[0], dict):
            return w
        updates = {}
        for k, v in row[0].items():
            if k in ("contact", "payoff") and isinstance(v, dict):
                updates[k] = {**getattr(w, k), **v}
            elif hasattr(w, k):
                updates[k] = v
        return replace(w, **updates)


def _payoff(consequence: dict, ref_decision: str | None, w: SimWeights) -> float:
    applies = ["nothing"]
    if ref_decision in ("foul", "yellow", "red", "penalty"):
        applies.append("foul")
    if consequence.get("opponent_booked") or ref_decision in ("yellow", "red"):
        applies.append("opponent_booked")
    if consequence.get("penalty_awarded") or ref_decision == "penalty":
        applies.append("penalty_won")
    if consequence.get("penalty_scored"):
        applies.append("penalty_scored")
    return max(w.payoff[a] for a in applies)


def flop_score(attrs, consequence: dict, ref_decision: str | None, confidence: float, weights: SimWeights) -> float:
    w = weights
    acting = (attrs.fake_pain if attrs.fake_pain is not None else w.default_fake_pain) / 10
    ground = 1 + math.log(1 + (attrs.time_on_ground_s or 0) / w.ground_scale_s)
    contact = w.contact[attrs.contact_level or "light"]
    bonus = 1 + w.roll_bonus * min(attrs.rolls or 0, w.max_rolls) + (w.miracle_bonus if attrs.miracle_recovery else 0)
    return w.base * acting * ground * contact * _payoff(consequence, ref_decision, w) * bonus * confidence


def entity_sim(scores_by_entity: dict[int, float], minutes_by_entity: dict[int, int], min_minutes: int = 270) -> dict[int, float]:
    """Flop score per 90 minutes, scaled so the top entity is 100. Under min_minutes: excluded."""
    per90 = {e: s / minutes_by_entity[e] * 90 for e, s in scores_by_entity.items()
             if minutes_by_entity.get(e, 0) >= min_minutes}
    top = max(per90.values(), default=0)
    return {e: (v / top * 100 if top else 0.0) for e, v in per90.items()}
