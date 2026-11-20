"""Linking API names/ids to our players, duplicate detection and nationality backfill."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import psycopg
from rapidfuzz import fuzz

from flopstats import review

SOURCE = "api-football"
FUZZY_MIN = 90
EXACT_CONFIDENCE = 0.95


@dataclass(frozen=True)
class LinkResult:
    player_id: int | None
    confidence: float
    method: str  # api_id | exact_name | fuzzy | none


def normalize_name(name: str) -> str:
    """Accent-free, case-folded, dots removed, whitespace collapsed."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.replace(".", " ")).strip().casefold()


def _api_player(conn, api_player_id: int | None) -> int | None:
    if api_player_id is None:
        return None
    row = conn.execute(
        "select entity_id from external_refs where entity_type = 'player' and source = %s "
        "and source_id = %s and status = 'linked'",
        (SOURCE, str(api_player_id)),
    ).fetchone()
    return row[0] if row else None


def link_event_player(
    conn: psycopg.Connection,
    match_id: int,
    team_id: int,
    api_player_id: int | None,
    name: str | None,
    *,
    event_id: int | None = None,
) -> LinkResult:
    """API id, then exact name in the team's lineup, then fuzzy name in the lineup, else review."""
    pid = _api_player(conn, api_player_id)
    if pid is not None:
        return LinkResult(pid, 1.0, "api_id")
    if api_player_id is None and not name:
        return LinkResult(None, 0.0, "none")  # nothing to link (e.g. a team-only event)

    lineup = conn.execute(
        "select p.id, p.display_name from match_lineups l join players p on p.id = l.player_id "
        "where l.match_id = %s and l.team_id = %s",
        (match_id, team_id),
    ).fetchall()
    scored: list[tuple[float, int, str]] = []
    if name:
        target = normalize_name(name)
        exact = [p for p in lineup if normalize_name(p[1]) == target]
        if len(exact) == 1:
            return LinkResult(exact[0][0], EXACT_CONFIDENCE, "exact_name")
        scored = sorted(
            ((fuzz.token_sort_ratio(target, normalize_name(n)), i, n) for i, n in lineup),
            key=lambda s: (-s[0], s[1]),
        )
        if not exact and scored and scored[0][0] >= FUZZY_MIN:
            best = scored[0]
            runner_up = scored[1][0] if len(scored) > 1 else -1
            if best[0] > runner_up:  # a tie is not a confident pick
                return LinkResult(best[1], best[0] / 100.0, "fuzzy")

    subject = ("match_event", event_id) if event_id is not None else ("match", match_id)
    done = conn.execute(
        "select resolution from review_items where kind = 'player_link' and subject_type = %s and subject_id = %s "
        "and status = 'resolved' order by resolved_at desc limit 1", subject).fetchone()
    if done is not None:  # Jamison already decided; never reopen it
        chosen = (done[0] or {}).get("player_id")
        return LinkResult(chosen, 1.0, "review") if chosen else LinkResult(None, 0.0, "none")

    review.create(
        conn,
        "player_link",
        "match_event" if event_id is not None else "match",
        event_id if event_id is not None else match_id,
        {
            "match_id": match_id,
            "team_id": team_id,
            "api_player_id": api_player_id,
            "name": name,
            "guesses": [{"player_id": i, "name": n, "score": round(s, 1)} for s, i, n in scored[:3]],
        },
    )
    return LinkResult(None, 0.0, "none")


def find_duplicate_players(conn: psycopg.Connection) -> list[tuple[int, int]]:
    """Pairs (lower id, higher id) with the same normalized name and the same birth date."""
    groups: dict[tuple[str, date], list[int]] = defaultdict(list)
    for pid, name, born in conn.execute(
        "select id, display_name, birth_date from players where birth_date is not null order by id"
    ):
        groups[(normalize_name(name), born)].append(pid)
    pairs = [(ids[0], other) for ids in groups.values() for other in ids[1:]]
    return sorted(pairs)


def backfill_nationality(conn: psycopg.Connection, client, season: int) -> int:
    """Fetch player details for players with no nationality; fill nationality, names, birth date.

    Returns how many players got a nationality. Calls go through the client's raw store,
    so a re-run makes no new HTTP calls for players already fetched.
    """
    from flopstats.apifootball.build import _upsert_ref

    todo = conn.execute(
        "select p.id, x.source_id from players p join external_refs x on x.entity_type = 'player' "
        "and x.entity_id = p.id and x.source = %s and x.status = 'linked' "
        "where p.nationality_country_id is null order by p.id",
        (SOURCE,),
    ).fetchall()
    filled = 0
    for player_id, api_id in todo:
        response = client.player(int(api_id), season)
        if not response:
            continue
        info = response[0].get("player") or {}
        nationality = info.get("nationality")
        born = (info.get("birth") or {}).get("date")
        with conn.transaction():
            country_id = _upsert_ref(conn, "country", nationality, "countries", {"name": nationality}) if nationality else None
            conn.execute(
                "update players set nationality_country_id = coalesce(%s, nationality_country_id), "
                "first_name = coalesce(%s, first_name), last_name = coalesce(%s, last_name), "
                "birth_date = coalesce(%s::date, birth_date) where id = %s",
                (country_id, info.get("firstname"), info.get("lastname"), born, player_id),
            )
        filled += country_id is not None
    return filled
