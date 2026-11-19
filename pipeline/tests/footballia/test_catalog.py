from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import respx

from flopstats.footballia.catalog import CatalogEntry, list_season, record_first_seen

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "footballia"
BASE = "https://footballia.eu/competitions/premier-league"


def _pages(mock):
    route = mock.get(BASE).mock(side_effect=lambda req: httpx.Response(
        200, text=(FIX / f"competition_p{req.url.params.get('page', '1')}.html").read_text()))
    return route


@respx.mock
def test_list_season_parses_fixture_html():
    route = _pages(respx)
    entries = list_season(httpx.Client(), "premier-league", "2024-2025", delay_s=0)
    assert [e.url for e in entries] == [
        "https://footballia.eu/matches/manchester-united-fulham-fc-premier-league",
        "https://footballia.eu/matches/brentford-fc-nottingham-forest-premier-league",
        "https://footballia.eu/matches/tottenham-hotspur-brighton-hove-albion-premier-league-2024-2025",
    ]
    e = entries[2]
    assert (e.home, e.away, e.date, e.competition, e.season, e.stage) == (
        "Tottenham Hotspur", "Brighton & Hove Albion", date(2025, 5, 25), "Premier League", "2024-2025", "Week 38")
    # Pages are walked newest-first and the walk stops at the page holding an older season.
    assert [r.request.url.params.get("page", "1") for r in route.calls] == ["1", "3", "2"]


@respx.mock
def test_list_season_latest_only():
    _pages(respx)
    entries = list_season(httpx.Client(), "premier-league", "2026-2027", delay_s=0)
    assert [e.home for e in entries] == ["Brighton & Hove Albion"]


def _entry(url="https://footballia.eu/matches/a-b"):
    return CatalogEntry(url=url, home="A", away="B", date=date(2025, 1, 1), competition="Premier League", season="2024-2025", stage="Week 20")


def test_record_first_seen_keeps_earliest_timestamp(db):
    t1 = datetime(2026, 11, 1, 8, tzinfo=UTC)
    t2 = datetime(2026, 11, 2, 8, tzinfo=UTC)
    assert record_first_seen(db, [_entry()], seen_at=t2) == 1
    assert record_first_seen(db, [_entry()], seen_at=t1) == 0  # not new...
    assert record_first_seen(db, [_entry(), _entry("https://footballia.eu/matches/c-d")], seen_at=t2) == 1
    payload = db.execute(
        "select payload from external_refs where entity_type = 'footballia_listing' and source = 'footballia' and source_id = %s",
        ("https://footballia.eu/matches/a-b",),
    ).fetchone()[0]
    # ...but an earlier sighting still moves first_seen_at back.
    assert datetime.fromisoformat(payload["first_seen_at"]) == t1
    assert payload["match_date"] == "2025-01-01" and payload["home"] == "A"
