"""Link a footballia listing to an API-Football match: date ±1 day plus normalized team names."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

import psycopg
from rapidfuzz import fuzz

from flopstats import review
from flopstats.footballia.catalog import CatalogEntry, record_first_seen

CONFIDENT = 0.95
ONE_DAY_OFF = 0.97
_STOPWORDS = {"fc", "afc", "cf", "the", "and"}

# Normalized name -> canonical key (canonical keys are normalized API-Football names).
# Seeded from the old repo's utils.map_team_name abbreviations, plus common long/short forms.
ALIASES = {
    "bou": "bournemouth", "ars": "arsenal", "avl": "aston villa", "bre": "brentford", "bha": "brighton",
    "che": "chelsea", "cry": "crystal palace", "eve": "everton", "ful": "fulham", "ips": "ipswich",
    "lei": "leicester", "liv": "liverpool", "mci": "manchester city", "mun": "manchester united",
    "new": "newcastle", "nfo": "nottingham forest", "sou": "southampton", "tot": "tottenham",
    "whu": "west ham", "wol": "wolves",
    "brighton hove albion": "brighton", "brighton hove": "brighton",
    "tottenham hotspur": "tottenham", "spurs": "tottenham",
    "wolverhampton wanderers": "wolves", "wolverhampton": "wolves",
    "newcastle united": "newcastle", "west ham united": "west ham", "ipswich town": "ipswich",
    "leicester city": "leicester", "manchester utd": "manchester united", "man utd": "manchester united",
    "man united": "manchester united", "man city": "manchester city", "nottm forest": "nottingham forest",
    "leeds united": "leeds", "luton town": "luton", "norwich city": "norwich", "stoke city": "stoke",
    "swansea city": "swansea", "cardiff city": "cardiff", "hull city": "hull",
    "huddersfield town": "huddersfield", "west bromwich albion": "west brom", "west bromwich": "west brom",
    "sheffield united": "sheffield utd",
}


@dataclass(frozen=True)
class MatchLink:
    match_id: int | None
    confidence: float


def normalize_team(name: str) -> str:
    text = html.unescape(html.unescape(name))
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", text.casefold()).split() if w not in _STOPWORDS]
    key = " ".join(words)
    return ALIASES.get(key, key)


def _team_score(a: str, b: str) -> float:
    return 1.0 if a == b else fuzz.token_sort_ratio(a, b) / 100.0


def link(conn: psycopg.Connection, entry: CatalogEntry) -> MatchLink:
    record_first_seen(conn, [entry])
    ref_id = conn.execute(
        "select id from external_refs where entity_type = 'footballia_listing' and source = 'footballia' and source_id = %s",
        (entry.url,),
    ).fetchone()[0]
    home, away = normalize_team(entry.home), normalize_team(entry.away)
    rows = conn.execute(
        """
        select m.id, h.name, a.name, (m.kickoff_at at time zone 'Europe/London')::date
        from matches m join teams h on h.id = m.home_team_id join teams a on a.id = m.away_team_id
        where (m.kickoff_at at time zone 'Europe/London')::date between %s and %s
        """,
        (entry.date - timedelta(days=1), entry.date + timedelta(days=1)),
    ).fetchall()
    scored = []
    for match_id, h, a, d in rows:
        date_factor = 1.0 if d == entry.date else ONE_DAY_OFF
        conf = min(_team_score(home, normalize_team(h)), _team_score(away, normalize_team(a))) * date_factor
        scored.append((round(conf, 4), match_id, h, a, d))
    scored.sort(key=lambda s: (-s[0], s[1]))
    confident = [s for s in scored if s[0] >= CONFIDENT]

    if len(confident) == 1:
        conf, match_id = confident[0][0], confident[0][1]
        with conn.transaction():
            conn.execute(
                "update external_refs set entity_id = %s, confidence = %s, status = 'linked' where id = %s",
                (match_id, conf, ref_id),
            )
        return MatchLink(match_id, conf)

    review.create(conn, "match_link", "footballia_listing", ref_id, {
        "url": entry.url, "home": entry.home, "away": entry.away, "date": entry.date.isoformat(),
        "guesses": [{"match_id": m, "home": h, "away": a, "date": d.isoformat(), "confidence": c}
                    for c, m, h, a, d in scored[:3]],
    })
    return MatchLink(None, scored[0][0] if scored else 0.0)
