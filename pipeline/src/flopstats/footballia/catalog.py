"""Footballia competition listings (public HTML, no login) and first-seen logging."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
import psycopg
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

BASE_URL = "https://footballia.eu"


@dataclass(frozen=True)
class CatalogEntry:
    url: str
    home: str
    away: str
    date: date
    competition: str
    season: str  # e.g. "2024-2025"
    stage: str = ""


def parse_listing(html: str) -> tuple[list[CatalogEntry], int]:
    """Rows of one listing page, plus the highest page number in its pagination."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[CatalogEntry] = []
    table = soup.select_one("table.table-search tbody")
    for tr in table.find_all("tr") if table else []:
        link = tr.select_one("td.match a[href]")
        names = [s.get_text(strip=True) for s in tr.select('td.match span[itemprop="name"]')]
        when = tr.select_one("td.playing_date")
        if not (link and len(names) >= 2 and when):
            continue
        cell = lambda cls: (tr.select_one(f"td.{cls}").get_text(strip=True) if tr.select_one(f"td.{cls}") else "")
        entries.append(CatalogEntry(
            url=BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
            home=names[0], away=names[1],
            date=datetime.strptime(when.get_text(strip=True), "%B %d, %Y").date(),
            competition=cell("competition"), season=cell("season"), stage=cell("stage"),
        ))
    pages = [int(p) for p in re.findall(r"[?&](?:amp;)?page=(\d+)", html)]
    return entries, max(pages, default=1)


def list_season(client: httpx.Client, league: str, season: str, *, delay_s: float = 1.0) -> list[CatalogEntry]:
    """Every listed match of `league` (footballia slug, e.g. "premier-league") in `season`.

    Listings run oldest first with no season filter, so walk pages newest-first and stop
    at the first page that reaches an older season.
    """
    url = f"{BASE_URL}/competitions/{league}"
    fetched: dict[int, list[CatalogEntry]] = {}

    def get(page: int) -> list[CatalogEntry]:
        if page not in fetched:
            if fetched:
                time.sleep(delay_s)  # be polite
            resp = client.get(url, params={"page": page} if page > 1 else None)
            resp.raise_for_status()
            fetched[page], last = parse_listing(resp.text)
            get.last = max(getattr(get, "last", 1), last)
        return fetched[page]

    get(1)
    found: list[CatalogEntry] = []
    for page in range(get.last, 0, -1):
        rows = get(page)
        found.extend(e for e in rows if e.season == season)
        if any(e.season < season for e in rows):
            break
    return sorted({e.url: e for e in found}.values(), key=lambda e: (e.date, e.url))


def record_first_seen(conn: psycopg.Connection, entries: list[CatalogEntry], seen_at: datetime | None = None) -> int:
    """Log each listing in external_refs; returns how many were new. Keeps the earliest sighting."""
    seen = (seen_at or datetime.now(UTC)).isoformat()
    new = 0
    with conn.transaction():
        for e in entries:
            payload = {"first_seen_at": seen, "home": e.home, "away": e.away, "match_date": e.date.isoformat(),
                       "season": e.season, "competition": e.competition, "stage": e.stage}
            inserted = conn.execute(
                """
                insert into external_refs (entity_type, source, source_id, status, payload)
                values ('footballia_listing', 'footballia', %s, 'needs_review', %s)
                on conflict (entity_type, source, source_id) do update set payload =
                  coalesce(external_refs.payload, '{}'::jsonb) || jsonb_build_object('first_seen_at', to_jsonb(least(
                    coalesce((external_refs.payload->>'first_seen_at')::timestamptz, (excluded.payload->>'first_seen_at')::timestamptz),
                    (excluded.payload->>'first_seen_at')::timestamptz)))
                returning (xmax = 0)
                """,
                (e.url, Jsonb(payload)),
            ).fetchone()[0]
            new += bool(inserted)
    return new
