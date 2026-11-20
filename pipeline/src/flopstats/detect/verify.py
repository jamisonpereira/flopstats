"""Structured verification of candidates by one or more verifier models.

Every (candidate, model) is paid for at most once: results (and invalid outputs) are stored
in `verifications` with their cost, and a stored model is never called again (Review Focus #3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from flopstats import costs

FlopType = Literal["dive", "exaggeration", "feigned_injury", "time_wasting"]


class _ModelText(BaseModel):
    """Model output is untrusted text: drop NUL characters, which Postgres text/jsonb can't store."""

    @field_validator("*", mode="before")
    @classmethod
    def _drop_nul(cls, v):
        return v.replace("\x00", "") if isinstance(v, str) else v


class PlayerGuess(_ModelText):
    team: Literal["home", "away"] | None = None
    shirt_number: int | None = None
    name: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class FlopAttrs(_ModelText):
    time_on_ground_s: float | None = Field(default=None, ge=0)
    rolls: int | None = Field(default=None, ge=0)
    fake_pain: int | None = Field(default=None, ge=1, le=10)
    clutched_part: str | None = None
    contact_part: str | None = None
    contact_level: Literal["none", "light", "real"] | None = None
    miracle_recovery: bool | None = None
    recovery_trigger: str | None = None
    pitch_x: float | None = Field(default=None, ge=0, le=100)
    pitch_y: float | None = Field(default=None, ge=0, le=100)
    pitch_conf: float | None = Field(default=None, ge=0, le=1)


class ModelAnswer(_ModelText):
    """What a verifier model must return (the JSON schema it is given)."""

    is_flop: bool
    type: FlopType | None = None
    confidence: float = Field(ge=0, le=1)
    start_s: float = Field(ge=0, description="seconds from the start of the clip")
    end_s: float = Field(ge=0, description="seconds from the start of the clip")
    is_replay: bool = False
    flopper: PlayerGuess = Field(default_factory=PlayerGuess)
    others: list[PlayerGuess] = Field(default_factory=list)
    attrs: FlopAttrs = Field(default_factory=FlopAttrs)
    ref_decision: Literal["none", "foul", "yellow", "red", "penalty"] = "none"


class VerifyResult(ModelAnswer):
    usd: Decimal = Decimal(0)
    model: str | None = None


@dataclass(frozen=True)
class LineupPlayer:
    team: Literal["home", "away"]
    shirt_number: int | None
    name: str


@dataclass(frozen=True)
class VerifyContext:
    lineups: list[LineupPlayer]
    home_team: str
    away_team: str
    kit_notes: str | None = None


def _call(v, segment: Path, context: VerifyContext):
    """One verifier call -> (result or None, answers to store, confidence, usd)."""
    from flopstats.detect.gemini import ContentBlocked, InvalidModelOutput

    try:
        res = v.verify(segment, context).model_copy(update={"model": v.name})
        return res, res.model_dump(mode="json"), res.confidence, res.usd
    except InvalidModelOutput as exc:
        return None, {"invalid": True, "error": str(exc)}, None, exc.usd
    except ContentBlocked as exc:  # same input is refused every time: store it, don't retry
        return None, {"invalid": True, "blocked": True, "error": str(exc)}, None, Decimal(0)


def run_many(
    conn: psycopg.Connection,
    items: list[tuple[int, Path]],
    verifiers: list,
    context: VerifyContext,
    *,
    workers: int = 1,
    run_id: int | None = None,
    match_id: int | None = None,
) -> dict[int, list[VerifyResult]]:
    """Every verifier once per (candidate, segment), up to `workers` calls at a time. Each answer is
    stored as soon as it arrives, so a crash keeps what was paid for. Returns each candidate's
    valid results in verifier order."""
    from flopstats.parallel import parallel

    ids = [cid for cid, _ in items]
    stored = {(cid, model): answers for cid, model, answers in conn.execute(
        "select candidate_id, model, answers from verifications where candidate_id = any(%s)", (ids,))}
    todo = [(cid, seg, v) for cid, seg in items for v in verifiers if (cid, v.name) not in stored]

    def call(job):
        cid, seg, v = job
        return cid, v, _call(v, seg, context)

    error = None
    try:
        for cid, v, (res, answers, confidence, usd) in parallel(call, todo, workers):
            with conn.transaction():
                conn.execute(
                    "insert into verifications (candidate_id, model, answers, confidence, usd) values (%s, %s, %s, %s, %s) "
                    "on conflict (candidate_id, model) do nothing",
                    (cid, v.name, Jsonb(answers), confidence, usd),
                )
                costs.record(conn, service="verify", model=v.name, units={"candidate_id": cid}, usd=usd,
                             idempotency_key=f"verify:{cid}:{v.name}", run_id=run_id, match_id=match_id)
            stored[(cid, v.name)] = answers
    except Exception as exc:
        error = exc
    if error is not None:
        raise error
    out: dict[int, list[VerifyResult]] = {}
    for cid in ids:
        out[cid] = [VerifyResult.model_validate(stored[(cid, v.name)]).model_copy(update={"model": v.name})
                    for v in verifiers if not stored[(cid, v.name)].get("invalid")]
    return out


def run(
    conn: psycopg.Connection,
    candidate_id: int,
    segment: Path,
    verifiers: list,
    context: VerifyContext,
    *,
    run_id: int | None = None,
    match_id: int | None = None,
) -> list[VerifyResult]:
    """Run every verifier once per candidate; return the valid results in verifier order."""
    return run_many(conn, [(candidate_id, segment)], verifiers, context, run_id=run_id, match_id=match_id)[candidate_id]


def primary(results: list[VerifyResult], primary_model: str) -> VerifyResult:
    for r in results:
        if r.model == primary_model:
            return r
    raise LookupError(f"no valid result from primary verifier {primary_model!r}")
