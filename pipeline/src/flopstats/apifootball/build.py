"""Build the clean football tables from stored API-Football raw responses.

Reads only `api_raw` (no HTTP). Every API entity is upserted through
`external_refs(source='api-football')`, so re-running changes nothing. Images keep only
their source URLs here; downloading them is stage 2.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg
from psycopg import sql

from flopstats.apifootball.client import params_hash
from flopstats.apifootball.linking import link_event_player

SOURCE = "api-football"


@dataclass
class BuildReport:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    needs_review: int = 0  # events whose player could not be linked (a review item exists)
    missing_details: int = 0  # fixtures in the season list with no stored detail
    null_player_events: int = 0  # events left with player_id null (includes team-only events)

    def __post_init__(self):
        self.counts = defaultdict(int, self.counts)
        self._seen: dict[str, set] = defaultdict(set)

    def see(self, table: str, key) -> None:
        """Count a row once per build, however many fixtures touch it."""
        if key not in self._seen[table]:
            self._seen[table].add(key)
            self.counts[table] += 1

    @property
    def null_player_pct(self) -> float:
        total = self.counts.get("match_events", 0)
        return 100.0 * self.null_player_events / total if total else 0.0


def normalize_referee(name: str) -> str:
    """'T. Robinson, England' -> 'T. Robinson'; collapse whitespace."""
    name = name.split(",", 1)[0]
    return re.sub(r"\s+", " ", name).strip()


def event_source_hash(fixture_id: int, event: dict) -> str:
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{fixture_id}:{canonical}".encode()).hexdigest()


# --- generic upserts --------------------------------------------------------------------


def _upsert_ref(conn: psycopg.Connection, entity_type: str, source_id: Any, table: str, values: dict) -> int:
    """Insert or update `table` for the API entity, keyed through external_refs."""
    source_id = str(source_id)
    cols = list(values)
    row = conn.execute(
        "select entity_id from external_refs where entity_type = %s and source = %s "
        "and source_id = %s and status = 'linked'",
        (entity_type, SOURCE, source_id),
    ).fetchone()
    if row and row[0] is not None:
        entity_id = row[0]
        targets = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
        ph = sql.SQL(", ").join(sql.Placeholder() * len(cols))
        updated = conn.execute(
            sql.SQL("update {t} set ({c}) = row({p}) where id = %s and ({c}) is distinct from ({p})").format(
                t=sql.Identifier(table), c=targets, p=ph
            ),
            [*values.values(), entity_id, *values.values()],
        )
        exists = updated.rowcount or conn.execute(
            sql.SQL("select 1 from {t} where id = %s").format(t=sql.Identifier(table)), (entity_id,)
        ).fetchone()
        if exists:
            return entity_id
    entity_id = conn.execute(
        sql.SQL("insert into {t} ({c}) values ({p}) returning id").format(
            t=sql.Identifier(table),
            c=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
            p=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        ),
        list(values.values()),
    ).fetchone()[0]
    conn.execute(
        "insert into external_refs (entity_type, entity_id, source, source_id, confidence, status) "
        "values (%s, %s, %s, %s, 1.0, 'linked') on conflict (entity_type, source, source_id) "
        "do update set entity_id = excluded.entity_id, confidence = 1.0, status = 'linked'",
        (entity_type, entity_id, SOURCE, source_id),
    )
    return entity_id


def _ref_id(conn: psycopg.Connection, entity_type: str, source_id: Any) -> int | None:
    if source_id is None:
        return None
    row = conn.execute(
        "select entity_id from external_refs where entity_type = %s and source = %s "
        "and source_id = %s and status = 'linked'",
        (entity_type, SOURCE, str(source_id)),
    ).fetchone()
    return row[0] if row else None


# --- raw loading ------------------------------------------------------------------------


def _load_raw(conn: psycopg.Connection, league: int, season: int) -> tuple[list[dict], dict[int, dict]]:
    row = conn.execute(
        "select body from api_raw where params_hash = %s",
        (params_hash("fixtures", {"league": league, "season": season}),),
    ).fetchone()
    if row is None:
        raise ValueError(f"season list for league {league} season {season} is not in api_raw; fetch it first")
    season_list = row[0]["response"]
    wanted = {f["fixture"]["id"] for f in season_list}
    details: dict[int, dict] = {}
    for (body,) in conn.execute(
        "select body from api_raw where endpoint = 'fixtures' and params ? 'ids' order by fetched_at, id"
    ):
        for f in body["response"]:
            if f["fixture"]["id"] in wanted:
                details[f["fixture"]["id"]] = f  # latest fetch wins
    return season_list, details


# --- build ------------------------------------------------------------------------------


def build_season(conn: psycopg.Connection, league_api_id: int, season_year: int) -> BuildReport:
    season_list, details = _load_raw(conn, league_api_id, season_year)
    report = BuildReport()
    if not season_list:
        return report
    first_id = season_list[0]["fixture"]["id"]
    lg = (details.get(first_id) or season_list[0])["league"]
    dates = [datetime.fromisoformat(f["fixture"]["date"]) for f in season_list]

    with conn.transaction():
        country_id = _upsert_ref(
            conn, "country", lg["country"], "countries",
            {"name": lg["country"], "flag_source_url": lg.get("flag")},
        )
        league_id = _upsert_ref(
            conn, "league", lg["id"], "leagues",
            {"name": lg["name"], "country_id": country_id, "logo_source_url": lg.get("logo")},
        )
        season_id = conn.execute(
            "insert into seasons (league_id, year, start_date, end_date) values (%s, %s, %s, %s) "
            "on conflict (league_id, year) do update set start_date = excluded.start_date, "
            "end_date = excluded.end_date where (seasons.start_date, seasons.end_date) "
            "is distinct from (excluded.start_date, excluded.end_date) returning id",
            (league_id, season_year, min(dates).date(), max(dates).date()),
        ).fetchone()
        if season_id is None:
            season_id = conn.execute(
                "select id from seasons where league_id = %s and year = %s", (league_id, season_year)
            ).fetchone()
        season_id = season_id[0]
        report.see("countries", country_id)
        report.see("leagues", league_id)
        report.see("seasons", season_id)

    home_venues: dict[int, Counter] = defaultdict(Counter)
    for listed in season_list:
        fid = listed["fixture"]["id"]
        f = details.get(fid)
        if f is None:
            report.missing_details += 1
            f = listed
        with conn.transaction():
            _build_fixture(conn, f, season_id, country_id, report, home_venues)

    with conn.transaction():
        for team_id, venues in home_venues.items():
            conn.execute(
                "update teams set venue_id = %s where id = %s and venue_id is distinct from %s",
                (venues.most_common(1)[0][0], team_id, venues.most_common(1)[0][0]),
            )
    return report


def _build_fixture(conn, f: dict, season_id: int, country_id: int, report: BuildReport, home_venues) -> None:
    fx = f["fixture"]
    fid = fx["id"]

    team_ids: dict[int, int] = {}
    for side in ("home", "away"):
        t = f["teams"][side]
        team_ids[t["id"]] = _upsert_ref(
            conn, "team", t["id"], "teams",
            {"name": t["name"], "country_id": country_id, "logo_source_url": t.get("logo")},
        )
        conn.execute(
            "insert into team_seasons (team_id, season_id) values (%s, %s) on conflict do nothing",
            (team_ids[t["id"]], season_id),
        )
        report.see("teams", team_ids[t["id"]])
        report.see("team_seasons", (team_ids[t["id"]], season_id))

    venue_id = None
    v = fx.get("venue") or {}
    if v.get("id") is not None:
        venue_id = _upsert_ref(
            conn, "venue", v["id"], "venues", {"name": v.get("name") or "?", "city": v.get("city"), "country_id": country_id}
        )
        home_venues[team_ids[f["teams"]["home"]["id"]]][venue_id] += 1
        report.see("venues", venue_id)

    referee_id = None
    if fx.get("referee"):
        name = normalize_referee(fx["referee"])
        if name:
            referee_id = conn.execute(
                "insert into referees (name) values (%s) on conflict (name) do update set name = excluded.name returning id",
                (name,),
            ).fetchone()[0]
            report.see("referees", referee_id)

    coach_ids: dict[int, int] = {}
    for lineup in f.get("lineups") or []:
        c = lineup.get("coach") or {}
        if c.get("id") is not None:
            coach_ids[lineup["team"]["id"]] = _upsert_ref(
                conn, "coach", c["id"], "coaches", {"name": c.get("name") or "?", "photo_source_url": c.get("photo")}
            )
            report.see("coaches", coach_ids[lineup["team"]["id"]])

    home_api, away_api = f["teams"]["home"]["id"], f["teams"]["away"]["id"]
    goals = f.get("goals") or {}
    match_id = _upsert_ref(
        conn, "match", fid, "matches",
        {
            "season_id": season_id,
            "home_team_id": team_ids[home_api],
            "away_team_id": team_ids[away_api],
            "kickoff_at": datetime.fromisoformat(fx["date"]),
            "venue_id": venue_id,
            "referee_id": referee_id,
            "home_coach_id": coach_ids.get(home_api),
            "away_coach_id": coach_ids.get(away_api),
            "round": f["league"].get("round"),
            "status": (fx.get("status") or {}).get("short"),
            "goals_home": goals.get("home"),
            "goals_away": goals.get("away"),
        },
    )
    report.see("matches", match_id)

    # Players: lineup gives starter/number/position; the players block gives full name + stats.
    lineup_info: dict[int, dict] = {}
    for lineup in f.get("lineups") or []:
        for key, starter in (("startXI", True), ("substitutes", False)):
            for entry in lineup.get(key) or []:
                p = entry["player"]
                if p.get("id") is not None:
                    lineup_info[p["id"]] = {"team": lineup["team"]["id"], "starter": starter, "number": p.get("number"),
                                            "pos": p.get("pos"), "name": p.get("name")}
    stats_info: dict[int, dict] = {}
    for block in f.get("players") or []:
        for entry in block.get("players") or []:
            p = entry["player"]
            if p.get("id") is not None:
                stats_info[p["id"]] = {"team": block["team"]["id"], "player": p,
                                       "stats": (entry.get("statistics") or [{}])[0]}

    for api_pid in lineup_info.keys() | stats_info.keys():
        li, si = lineup_info.get(api_pid, {}), stats_info.get(api_pid)
        pl = si["player"] if si else {}
        st = si["stats"] if si else {}
        games = st.get("games") or {}
        team_api = (si or li)["team"]
        if team_api not in team_ids:
            continue
        player_id = _upsert_ref(
            conn, "player", api_pid, "players",
            {"display_name": pl.get("name") or li.get("name") or "?", "photo_source_url": pl.get("photo")},
        )
        report.see("players", player_id)
        number = li.get("number") if li.get("number") is not None else games.get("number")
        position = li.get("pos") or games.get("position")
        conn.execute(
            "insert into player_team_seasons (player_id, team_id, season_id, shirt_number, position) "
            "values (%s, %s, %s, %s, %s) on conflict (player_id, team_id, season_id) do update set "
            "shirt_number = excluded.shirt_number, position = excluded.position "
            "where (player_team_seasons.shirt_number, player_team_seasons.position) "
            "is distinct from (excluded.shirt_number, excluded.position)",
            (player_id, team_ids[team_api], season_id, number, position),
        )
        report.see("player_team_seasons", (player_id, team_ids[team_api], season_id))
        fouls, cards, pen = st.get("fouls") or {}, st.get("cards") or {}, st.get("penalty") or {}
        cols = {
            "team_id": team_ids[team_api],
            "is_starter": li.get("starter", games.get("substitute") is False),
            "shirt_number": number,
            "position": position,
            "minutes_played": games.get("minutes"),
            "fouls_drawn": fouls.get("drawn"),
            "fouls_committed": fouls.get("committed"),
            "yellow_cards": cards.get("yellow"),
            "red_cards": cards.get("red"),
            "penalties_won": pen.get("won"),
            "penalties_committed": pen.get("commited", pen.get("committed")),  # API spells it "commited"
            "penalties_scored": pen.get("scored"),
            "penalties_missed": pen.get("missed"),
        }
        names = list(cols)
        conn.execute(
            sql.SQL(
                "insert into match_lineups (match_id, player_id, {c}) values (%s, %s, {p}) "
                "on conflict (match_id, player_id) do update set ({c}) = row({ex}) "
                "where ({cur}) is distinct from ({ex})"
            ).format(
                c=sql.SQL(", ").join(sql.Identifier(n) for n in names),
                p=sql.SQL(", ").join(sql.Placeholder() * len(names)),
                ex=sql.SQL(", ").join(sql.SQL("excluded.{}").format(sql.Identifier(n)) for n in names),
                cur=sql.SQL(", ").join(sql.SQL("match_lineups.{}").format(sql.Identifier(n)) for n in names),
            ),
            [match_id, player_id, *cols.values()],
        )
        report.see("match_lineups", (match_id, player_id))

    for event in f.get("events") or []:
        team_api = (event.get("team") or {}).get("id")
        if team_api not in team_ids:
            continue
        player = event.get("player") or {}
        assist_api = (event.get("assist") or {}).get("id")
        t = event.get("time") or {}
        source_hash = event_source_hash(fx["id"], event)
        row = conn.execute(
            "insert into match_events (match_id, team_id, minute, extra_minute, type, detail, comments, "
            "source_hash) values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict (source_hash) do nothing "
            "returning id",
            (match_id, team_ids[team_api], t.get("elapsed"), t.get("extra"), event.get("type") or "?",
             event.get("detail"), event.get("comments"), source_hash),
        ).fetchone()
        event_id = row[0] if row else conn.execute(
            "select id from match_events where source_hash = %s", (source_hash,)
        ).fetchone()[0]
        link = link_event_player(
            conn, match_id, team_ids[team_api], player.get("id"), player.get("name"), event_id=event_id
        )
        if link.player_id is None and (player.get("id") is not None or player.get("name")):
            report.needs_review += 1
        if link.player_id is None:
            report.null_player_events += 1
        # Assists (and the incoming player on a substitution) link by API id only.
        assist_id = _ref_id(conn, "player", assist_api)
        conn.execute(
            # coalesce: a rebuild never erases a player set earlier (e.g. by a review decision).
            "update match_events set player_id = coalesce(%s, player_id), assist_player_id = coalesce(%s, assist_player_id) "
            "where id = %s and (player_id, assist_player_id) is distinct from "
            "(coalesce(%s::bigint, player_id), coalesce(%s::bigint, assist_player_id))",
            (link.player_id, assist_id, event_id, link.player_id, assist_id),
        )
        report.see("match_events", event_id)
