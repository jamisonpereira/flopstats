"""Stage 1 pass criteria: precision, known-dive recall, verifier comparison, cost projection."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import psycopg

FLOP_DECISIONS = ("confirm", "change_type")  # Jamison says: it is a flop
VERDICT_DECISIONS = ("confirm", "change_type", "reject")
COUNTED_STATUSES = ("confirmed", "review")
WITHIN_S = 60


@dataclass(frozen=True)
class Precision:
    agreed: int
    reviewed: int
    rate: float


@dataclass(frozen=True)
class Recall:
    found: int
    total: int
    missed: list[dict]

    @property
    def rate(self) -> float:
        return self.found / self.total if self.total else 0.0


@dataclass(frozen=True)
class VerifierStats:
    model: str
    agreed_with_jamison: int
    reviewed: int
    usd_per_match: float


_LATEST_VERDICT = """
    select distinct on (r.incident_id) r.incident_id, r.decision
    from reviews r join incidents i on i.id = r.incident_id
    where i.run_id = %s and r.decision = any(%s)
    order by r.incident_id, r.at desc, r.id desc
"""


def _matches_in_run(conn: psycopg.Connection, run_id: int) -> list[int]:
    """Matches whose windows were scored in this run."""
    return [r[0] for r in conn.execute(
        "select distinct v.match_id from jobs j join videos v on j.key = %s || ':' || v.id || ':score' "
        "where j.kind = 'score' and j.status = 'done' and v.match_id is not null",
        (str(run_id),),
    )]


def precision(conn: psycopg.Connection, run_id: int) -> Precision:
    """Of the flops the AI confirmed by itself (confirmed or ai_judged) that Jamison judged, the share he agreed with."""
    rows = conn.execute(
        f"select v.decision from ({_LATEST_VERDICT}) v join incidents i on i.id = v.incident_id "
        "where i.ai_status in ('confirmed', 'ai_judged')",
        (run_id, list(VERDICT_DECISIONS)),
    ).fetchall()
    agreed = sum(1 for (d,) in rows if d in FLOP_DECISIONS)
    return Precision(agreed, len(rows), agreed / len(rows) if rows else 0.0)


def known_dive_recall(conn: psycopg.Connection, run_id: int) -> Recall:
    """Known dives: cards for simulation and VAR-cancelled penalties. Found = a confirmed or
    review incident within 60 s (event minutes are elapsed minutes: minute m = clock (m-1):00-m:00)."""
    matches = _matches_in_run(conn, run_id)
    if not matches:
        return Recall(0, 0, [])
    events = conn.execute(
        """
        select e.id, e.match_id, e.minute, e.extra_minute, e.type, e.detail, e.comments, p.display_name
        from match_events e left join players p on p.id = e.player_id
        where e.match_id = any(%s)
          and ((e.type = 'Card' and e.comments ilike 'Simulation%%') or (e.type = 'Var' and e.detail = 'Penalty cancelled'))
        order by e.match_id, e.minute, e.extra_minute nulls first, e.id
        """,
        (matches,),
    ).fetchall()
    found, missed = 0, []
    for eid, mid, minute, extra, etype, detail, comments, player in events:
        m = (minute or 0) + (extra or 0)
        lo, hi = (m - 1) * 60 - WITHIN_S, m * 60 + WITHIN_S
        hit = conn.execute(
            "select 1 from incidents where run_id = %s and match_id = %s and status = any(%s) "
            "and game_minute is not null and game_minute * 60 + coalesce(game_second, 0) between %s and %s limit 1",
            (run_id, mid, list(COUNTED_STATUSES), lo, hi),
        ).fetchone()
        if hit:
            found += 1
        else:
            missed.append({"event_id": eid, "match_id": mid, "minute": minute, "extra_minute": extra, "type": etype,
                           "detail": detail, "comments": comments, "player": player})
    return Recall(found, len(events), missed)


def verifier_comparison(conn: psycopg.Connection, run_id: int) -> list[VerifierStats]:
    """Each verifier's is_flop against Jamison's verdict on the incidents he judged."""
    n_matches = max(len(_matches_in_run(conn, run_id)), 1)
    verdicts = dict(conn.execute(_LATEST_VERDICT, (run_id, list(VERDICT_DECISIONS))).fetchall())
    out = []
    for (model,) in conn.execute(
            "select distinct v.model from verifications v join candidates c on c.id = v.candidate_id where c.run_id = %s order by 1",
            (run_id,)).fetchall():
        rows = conn.execute(
            "select i.id, (v.answers->>'is_flop')::boolean from incidents i join verifications v on v.candidate_id = i.candidate_id "
            "where i.run_id = %s and v.model = %s and not coalesce((v.answers->>'invalid')::boolean, false)",
            (run_id, model),
        ).fetchall()
        judged = [(iid, is_flop) for iid, is_flop in rows if iid in verdicts]
        agreed = sum(1 for iid, is_flop in judged if is_flop == (verdicts[iid] in FLOP_DECISIONS))
        usd = conn.execute(
            "select coalesce(sum(v.usd), 0) from verifications v join candidates c on c.id = v.candidate_id where c.run_id = %s and v.model = %s",
            (run_id, model),
        ).fetchone()[0]
        out.append(VerifierStats(model, agreed, len(judged), float(usd) / n_matches))
    return out


def cost_projection(conn: psycopg.Connection, run_id: int, matches_total: int) -> Decimal:
    """Spend per processed match so far × matches_total."""
    n = len(_matches_in_run(conn, run_id))
    if not n:
        return Decimal(0)
    spent = conn.execute("select coalesce(sum(usd), 0) from cost_ledger where run_id = %s", (run_id,)).fetchone()[0]
    return (Decimal(spent) / n * matches_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
