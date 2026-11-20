"""Turn a verified flop into an incident: game time, players, consequence, SIM, review items."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb
from rapidfuzz import fuzz

from flopstats import review
from flopstats.apifootball.linking import normalize_name
from flopstats.detect import decide, dedupe, sim
from flopstats.detect.verify import PlayerGuess, VerifyResult
from flopstats.video.timesync import SyncResult, to_game_time

PENALTY_LOOKAHEAD_S = 180  # the API logs a penalty at the kick, often 1-2 min after the award
LOOKAHEAD_S = 60
NAME_MIN = 85


@dataclass(frozen=True)
class LineupEntry:
    player_id: int
    team_id: int
    shirt_number: int | None
    name: str


@dataclass(frozen=True)
class EventRow:
    minute: int | None
    extra_minute: int | None
    type: str
    detail: str | None
    comments: str | None
    team_id: int | None


@dataclass(frozen=True)
class MatchContext:
    id: int
    home_team_id: int
    away_team_id: int
    lineup: list[LineupEntry]
    events: list[EventRow]


@dataclass(frozen=True)
class CandidateRef:
    id: int
    video_id: int
    start_s: float  # where the candidate's segment starts in the video


@dataclass(frozen=True)
class DecideConfig:
    confirm_t: float
    review_t: float
    review_cap: int | None
    min_player_conf: float
    weights: sim.SimWeights


@dataclass(frozen=True)
class Attribution:
    player_id: int | None
    confidence: float
    guesses: list[dict]


def attribute(guess: PlayerGuess, lineup: list[LineupEntry], team_id: int | None, min_conf: float) -> Attribution:
    """Shirt number within the team's lineup, then name. Unsure or no match -> top 3 guesses."""
    team = [p for p in lineup if p.team_id == team_id]
    target = normalize_name(guess.name) if guess.name else None

    def name_score(p: LineupEntry) -> float:
        return fuzz.partial_token_sort_ratio(target, normalize_name(p.name)) if target else 0.0

    def rank(p: LineupEntry):
        shirt_gap = abs(p.shirt_number - guess.shirt_number) if None not in (p.shirt_number, guess.shirt_number) else 99
        return (-(p.shirt_number == guess.shirt_number and guess.shirt_number is not None), -name_score(p), shirt_gap, p.player_id)

    ranked = sorted(team, key=rank)
    guesses = [{"player_id": p.player_id, "team_id": p.team_id, "name": p.name, "shirt_number": p.shirt_number,
                "name_score": round(name_score(p), 1)} for p in ranked[:3]]
    match, conf = None, 0.0
    if guess.shirt_number is not None:
        by_shirt = [p for p in team if p.shirt_number == guess.shirt_number]
        if len(by_shirt) == 1:
            match, conf = by_shirt[0], guess.confidence
    if match is None and target:
        best = max(team, key=name_score, default=None)
        if best is not None and name_score(best) >= NAME_MIN:
            match, conf = best, guess.confidence * name_score(best) / 100
    if match is None or conf < min_conf:
        return Attribution(None, conf, guesses)
    return Attribution(match.player_id, conf, guesses)


def _overlaps(e: EventRow, start_clock: float, end_clock: float) -> bool:
    """API minutes are elapsed minutes: minute m covers clock (m-1)*60 .. m*60."""
    if e.minute is None:
        return False
    m = e.minute + (e.extra_minute or 0)
    return (m - 1) * 60 <= end_clock and m * 60 >= start_clock


def consequence(match_events: list[EventRow], game_minute: int, game_second: int, team_id: int | None) -> dict:
    t = game_minute * 60 + game_second
    near = [e for e in match_events if _overlaps(e, t, t + LOOKAHEAD_S)]
    pen = [e for e in match_events if _overlaps(e, t, t + PENALTY_LOOKAHEAD_S)
           and e.team_id == team_id and (e.type or "").lower() == "goal" and "penalty" in (e.detail or "").lower()]
    return {
        "penalty_awarded": bool(pen),
        "penalty_scored": any((e.detail or "").lower() == "penalty" for e in pen),
        "opponent_booked": any((e.type or "").lower() == "card" and e.team_id is not None and e.team_id != team_id for e in near),
        "goal_within_60s": any((e.type or "").lower() == "goal" and e.team_id == team_id
                               and (e.detail or "").lower() == "normal goal" for e in near),  # penalties have their own keys
    }


def persist(conn: psycopg.Connection, run_id: int, candidate: CandidateRef, result: VerifyResult, sync: SyncResult,
            match: MatchContext, config: DecideConfig) -> int:
    """Write one incident (+ players, review items). Idempotent through dedupe_key."""
    key = dedupe.key(result, candidate.start_s)
    existing = conn.execute(
        "select id from incidents where run_id = %s and video_id = %s and dedupe_key = %s", (run_id, candidate.video_id, key)
    ).fetchone()
    if existing:
        return existing[0]
    side = {"home": match.home_team_id, "away": match.away_team_id}
    team_id = side.get(result.flopper.team)
    opponent = {match.home_team_id: match.away_team_id, match.away_team_id: match.home_team_id}.get(team_id)
    v_start, v_end = candidate.start_s + result.start_s, candidate.start_s + result.end_s
    gt = to_game_time(v_start, sync)
    cons = consequence(match.events, gt[0], gt[1], team_id) if gt else {}
    score = sim.flop_score(result.attrs, cons, result.ref_decision, result.confidence, config.weights)

    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"incident-review:{run_id}:{match.id}",))
        in_review = conn.execute(
            "select count(*) from incidents where run_id = %s and match_id = %s and status = 'review'", (run_id, match.id)
        ).fetchone()[0]
        st = decide.status(result.confidence, config.confirm_t, config.review_t, config.review_cap, in_review)
        incident_id = conn.execute(
            """
            insert into incidents (run_id, match_id, video_id, candidate_id, type, video_start_s, video_end_s,
              game_minute, game_second, team_id, confidence, status, attrs, ref_decision, ref_penalized_team_id,
              consequence, sim_score, dedupe_key)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (run_id, video_id, dedupe_key) do nothing returning id
            """,
            (run_id, match.id, candidate.video_id, candidate.id, result.type or "dive", v_start, max(v_end, v_start),
             gt[0] if gt else None, gt[1] if gt else None, team_id, result.confidence, st,
             Jsonb(result.attrs.model_dump(exclude_none=True)), result.ref_decision,
             opponent if result.ref_decision != "none" else None, Jsonb(cons) if cons else None, score, key),
        ).fetchone()
        if incident_id is None:  # a concurrent writer got there first
            return conn.execute("select id from incidents where run_id = %s and video_id = %s and dedupe_key = %s",
                                (run_id, candidate.video_id, key)).fetchone()[0]
        incident_id = incident_id[0]

        flopper = attribute(result.flopper, match.lineup, team_id, config.min_player_conf)
        if team_id is not None:
            conn.execute(
                "insert into incident_players (incident_id, player_id, team_id, role, confidence, guesses) values (%s, %s, %s, 'flopper', %s, %s)",
                (incident_id, flopper.player_id, team_id, flopper.confidence, Jsonb(flopper.guesses)),
            )
        for other in result.others:
            other_team = side.get(other.team)
            if other_team is None:
                continue
            a = attribute(other, match.lineup, other_team, config.min_player_conf)
            role = "alleged_fouler" if other_team == opponent else "other"
            conn.execute(
                "insert into incident_players (incident_id, player_id, team_id, role, confidence, guesses) values (%s, %s, %s, %s, %s, %s)",
                (incident_id, a.player_id, other_team, role, a.confidence, Jsonb(a.guesses)),
            )

    if st == "review":
        review.create(conn, "flop_verdict", "incident", incident_id, {"confidence": result.confidence, "type": result.type})
    if st != "rejected" and flopper.player_id is None:
        review.create(conn, "flop_player", "incident", incident_id, {
            "team_id": team_id, "guess": result.flopper.model_dump(), "guesses": flopper.guesses})
    return incident_id
